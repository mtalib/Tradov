#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_IBKRLoginLauncher_OAuth.py
Purpose: Enhanced GUI launcher for SPYDER Trading System with OAuth 2.0 JWT authentication

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-23 Time: 12:30:00
Version: 2.0.0

Module Description:
    Enhanced launcher for the SPYDER trading system that provides:
    - Dashboard Only (visualization mode)
    - IBKR Web API - Paper Trading (OAuth 2.0 with JWT)
    - IBKR Web API - Live Trading (OAuth 2.0 with JWT)

    Features:
    - OAuth 2.0 with JWT authentication (private_key_jwt client authentication)
    - Private key file selection and validation
    - Client ID and account configuration
    - Access token management and status monitoring
    - Automatic token refresh before expiration
    - Remember configuration options
    - Session timeout warnings
    - About dialog with version info

    Configuration parameters are requested for Paper/Live trading modes.
    No more IB Gateway option - only IBKR Web API is supported.

Dependencies:
    - tkinter for GUI
    - SpyderU_Utilities for logging
    - SpyderB_Broker for IBKR Web API
    - cryptography for JWT generation
    - requests for OAuth token requests
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import subprocess
import configparser
import threading
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

# ==============================================================================
# THIRD-PARTY IMPORTS - OAuth and Cryptography
# ==============================================================================
try:
    import jwt
    import requests
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend

    HAS_CRYPTO = True
except ImportError as import_error:
    HAS_CRYPTO = False
    print(f"ERROR: Required OAuth dependencies not installed: {import_error}")
    print("Please install: pip install PyJWT cryptography requests")
    sys.exit(1)

# ==============================================================================
# THIRD-PARTY IMPORTS - GUI
# ==============================================================================
try:
    import tkinter as tk
    from tkinter import messagebox, filedialog

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

    def get_logger(name):
        """Fallback logger creation"""
        return logging.getLogger(name)


# ==============================================================================
# CONSTANTS
# ==============================================================================
VERSION = "2.0.0"
BUILD_DATE = "2025-10-23"

SPYDER_HOME = project_root  # Use dynamically determined project root
CONFIG_DIR = SPYDER_HOME / "config"
CONFIG_FILE = CONFIG_DIR / "launcher_config_oauth.ini"

# IBKR Client Portal Gateway endpoints (local)
CLIENT_PORTAL_BASE = "https://localhost:5000"
OAUTH_ENDPOINT = f"{CLIENT_PORTAL_BASE}/v1/api/oauth"
TOKEN_ENDPOINT = "/token"

# Session timeout in minutes
SESSION_TIMEOUT = 30

# Tooltips
TOOLTIPS = {
    "dashboard": "Launch the dashboard in visualization mode only.\n"
    "No connection to Interactive Brokers.\n"
    "Uses simulated market data for testing and analysis.",
    "paper": "Connect to IBKR using Web API in Paper Trading mode.\n"
    "Safe simulation environment with virtual money.\n"
    "All features available without financial risk.\n"
    "Requires OAuth 2.0 with JWT configuration.",
    "live": "Connect to IBKR using Web API in Live Trading mode.\n"
    "⚠️ REAL MONEY TRADING - Uses actual funds ⚠️\n"
    "Requires verified IBKR Live Trading account.\n"
    "Exercise caution - financial risk involved.",
    "client_id": "OAuth Client ID provided by IBKR.\n"
    "Usually starts with 'l' followed by numbers.",
    "account_id": "IBKR Account ID to use for trading.\n"
    "Format: DU followed by 7 digits (e.g., DU1234567).",
    "private_key": "Private key file for JWT signing.\n"
    "Must be in PEM format.\n"
    "Generated using: openssl genpkey -algorithm RSA -out private_key.pem -pkcs8",
    "environment": "IBKR API environment.\n"
    "Use 'live' for live trading or 'paper' for paper trading.",
}

DEFAULT_CONFIG = {
    "last_mode": "dashboard",
    "remember_paper_client_id": "",
    "remember_paper_account_id": "",
    "remember_paper_private_key": "",
    "remember_paper_environment": "paper",
    "remember_live_client_id": "",
    "remember_live_account_id": "",
    "remember_live_private_key": "",
    "remember_live_environment": "live",
    "save_paper_config": "false",
    "save_live_config": "false",
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

    def show_tooltip(self, event=None):  # pylint: disable=unused-argument
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
            pady=8,
        )
        label.pack()

    def hide_tooltip(self, event=None):  # pylint: disable=unused-argument
        """Hide tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# ==============================================================================
# OAUTH AUTHENTICATION CLASS
# ==============================================================================
class IBKROAuthManager:
    """
    Manages OAuth 2.0 with JWT authentication for IBKR Web API
    """

    def __init__(self, logger=None):
        """Initialize OAuth manager"""
        self.logger = logger or logging.getLogger(__name__)
        self.access_token = None
        self.token_expires_at = None

    def generate_jwt(self, client_id: str, private_key_path: str) -> Optional[str]:
        """
        Generate JWT for client authentication

        Args:
            client_id: OAuth client ID
            private_key_path: Path to private key file

        Returns:
            JWT token or None if failed
        """
        try:
            # Load private key
            with open(private_key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(), password=None, backend=default_backend()
                )

            # Create JWT payload
            now = datetime.utcnow()
            payload = {
                "iss": client_id,  # Issuer (client ID)
                "sub": client_id,  # Subject (client ID)
                "aud": OAUTH_ENDPOINT,  # Audience
                "exp": now + timedelta(minutes=5),  # Expiration (5 minutes)
                "iat": now,  # Issued at
            }

            # Generate JWT
            token = jwt.encode(payload, private_key, algorithm="RS256")

            self.logger.info("JWT generated successfully")
            return token

        except IOError as io_err:
            self.logger.error("Failed to read private key file: %s", io_err)
            return None
        except ValueError as val_err:
            self.logger.error("Invalid private key format: %s", val_err)
            return None
        except Exception as gen_err:
            self.logger.error("Failed to generate JWT: %s", gen_err)
            return None

    def get_access_token(
        self, client_id: str, private_key_path: str, environment: str = "paper"
    ) -> Optional[str]:
        """
        Get access token using OAuth 2.0 with JWT

        Args:
            client_id: OAuth client ID
            private_key_path: Path to private key file
            environment: 'paper' or 'live'

        Returns:
            Access token or None if failed
        """
        try:
            # Generate JWT
            assertion = self.generate_jwt(client_id, private_key_path)
            if not assertion:
                return None

            # Determine endpoint URL based on environment
            if environment.lower() == "live":
                token_url = f"{OAUTH_ENDPOINT}/live{TOKEN_ENDPOINT}"
            else:
                token_url = f"{OAUTH_ENDPOINT}/paper{TOKEN_ENDPOINT}"

            # Prepare token request
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "client_id": client_id,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
            }

            # Request access token with timeout
            response = requests.post(
                token_url, headers=headers, data=data, verify=True, timeout=30
            )

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour

                # Calculate token expiration time
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                self.logger.info(
                    "Access token obtained, expires at %s", self.token_expires_at
                )
                return self.access_token

            self.logger.error(
                "Token request failed: %s - %s", response.status_code, response.text
            )
            return None

        except requests.exceptions.Timeout as timeout_err:
            self.logger.error("Token request timed out: %s", timeout_err)
            return None
        except requests.exceptions.RequestException as req_err:
            self.logger.error("Token request failed: %s", req_err)
            return None
        except Exception as gen_err:
            self.logger.error("Failed to get access token: %s", gen_err)
            return None

    def is_token_valid(self) -> bool:
        """Check if current access token is valid"""
        if not self.access_token or not self.token_expires_at:
            return False

        # Add 5-minute buffer before expiration
        buffer_time = timedelta(minutes=5)
        return datetime.now() + buffer_time < self.token_expires_at

    def validate_configuration(
        self, client_id: str, account_id: str, private_key_path: str, environment: str
    ) -> Tuple[bool, str]:
        """
        Validate OAuth configuration

        Args:
            client_id: OAuth client ID
            account_id: IBKR account ID
            private_key_path: Path to private key file
            environment: 'paper' or 'live'

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Validate client ID
            if not client_id or not client_id.startswith("l"):
                return (
                    False,
                    "Invalid Client ID. Must start with 'l' followed by numbers.",
                )

            # Validate account ID
            if (
                not account_id
                or not account_id.startswith("DU")
                or len(account_id) != 9
            ):
                return False, "Invalid Account ID. Must be in format DU1234567."

            # Validate environment
            if environment.lower() not in ["paper", "live"]:
                return False, "Invalid Environment. Must be 'paper' or 'live'."

            # Validate private key file
            if not os.path.exists(private_key_path):
                return False, f"Private key file not found: {private_key_path}"

            # Try to load private key
            with open(private_key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(), password=None, backend=default_backend()
                )

            # Validate private key is RSA
            if not isinstance(private_key, rsa.RSAPrivateKey):
                return False, "Private key must be RSA algorithm."

            return True, ""

        except IOError as io_err:
            return False, f"Cannot read private key file: {str(io_err)}"
        except ValueError as val_err:
            return False, f"Invalid private key format: {str(val_err)}"
        except Exception as gen_err:
            return False, f"Configuration validation error: {str(gen_err)}"


# ==============================================================================
# ENHANCED LAUNCHER CLASS
# ==============================================================================
class SpyderOAuthLauncher:
    """
    SPYDER Trading System Enhanced Launcher with OAuth 2.0 JWT authentication.

    Provides three launch modes:
    1. Dashboard Only - No IBKR connection
    2. IBKR Web API - Paper Trading (requires OAuth configuration)
    3. IBKR Web API - Live Trading (requires OAuth configuration)
    """

    def __init__(self):
        """Initialize the launcher"""
        # Setup logging
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info("Initializing SPYDER OAuth Launcher v%s", VERSION)

        # Load configuration
        self.config = self._load_configuration()

        # OAuth manager
        self.oauth_manager = IBKROAuthManager(self.logger)

        # Connection status
        self.connection_status = (
            "disconnected"  # disconnected, checking, connected, error
        )
        self.connection_check_thread = None

        # Initialize GUI
        self.root = tk.Tk()
        self.root.title("SPYDER Trading System - OAuth Launch Options")
        self.root.geometry("800x750")  # Wider window for OAuth fields
        self.root.resizable(False, False)

        # Center window on screen
        self._center_window()

        # Setup variables
        self.launch_mode = tk.StringVar(value=self.config.get("SPYDER", "last_mode"))

        # Paper trading OAuth configuration
        self.paper_client_id = tk.StringVar(
            value=self.config.get("SPYDER", "remember_paper_client_id")
        )
        self.paper_account_id = tk.StringVar(
            value=self.config.get("SPYDER", "remember_paper_account_id")
        )
        self.paper_private_key = tk.StringVar(
            value=self.config.get("SPYDER", "remember_paper_private_key")
        )
        self.paper_environment = tk.StringVar(
            value=self.config.get(
                "SPYDER", "remember_paper_environment", fallback="paper"
            )
        )
        self.save_paper_config = tk.BooleanVar(
            value=self.config.get("SPYDER", "save_paper_config") == "true"
        )

        # Live trading OAuth configuration
        self.live_client_id = tk.StringVar(
            value=self.config.get("SPYDER", "remember_live_client_id")
        )
        self.live_account_id = tk.StringVar(
            value=self.config.get("SPYDER", "remember_live_account_id")
        )
        self.live_private_key = tk.StringVar(
            value=self.config.get("SPYDER", "remember_live_private_key")
        )
        self.live_environment = tk.StringVar(
            value=self.config.get(
                "SPYDER", "remember_live_environment", fallback="live"
            )
        )
        self.save_live_config = tk.BooleanVar(
            value=self.config.get("SPYDER", "save_live_config") == "true"
        )

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
            except (IOError, configparser.Error) as err:
                self.logger.error("Error loading config: %s", err)
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
            with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
                config.write(config_file)
            self.logger.info("Configuration saved to %s", CONFIG_FILE)
        except (IOError, OSError) as err:
            self.logger.error("Failed to save configuration: %s", err)

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
                self.logger.warning(
                    "Session timeout detected (%d minutes)", elapsed.seconds // 60
                )

                # Clear saved private keys for security
                if self.config.get("SPYDER", "save_paper_config") == "true":
                    self.paper_private_key.set("")
                    self.config.set("SPYDER", "remember_paper_private_key", "")

                if self.config.get("SPYDER", "save_live_config") == "true":
                    self.live_private_key.set("")
                    self.config.set("SPYDER", "remember_live_private_key", "")

                self._save_configuration()

                messagebox.showinfo(
                    "Session Timeout",
                    f"Your saved session has expired after {timeout_minutes} minutes of inactivity.\n\n"
                    "Please re-enter your configuration for security.",
                )
        except (ValueError, OSError) as err:
            self.logger.error("Session timeout check failed: %s", err)

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
            "bg": bg_color,
            "fg": fg_color,
            "accent": accent_color,
            "input_bg": input_bg,
            "frame_bg": frame_bg,
        }

    def _create_widgets(self) -> None:
        """Create main launcher widgets"""
        main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header with About button
        header_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        header_frame.pack(fill=tk.X, pady=(0, 10))

        header = tk.Label(
            header_frame,
            text="🕷️ SPYDER AUTONOMOUS OPTIONS TRADING SYSTEM",
            font=("Arial", 16, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["accent"],
        )
        header.pack(side=tk.LEFT)

        # About button
        about_btn = tk.Button(
            header_frame,
            text="?",
            font=("Arial", 12, "bold"),
            bg=self.colors["frame_bg"],
            fg=self.colors["accent"],
            activebackground=self.colors["input_bg"],
            relief=tk.FLAT,
            width=2,
            height=1,
            cursor="hand2",
            command=self.show_about,
        )
        about_btn.pack(side=tk.RIGHT)
        ToolTip(about_btn, "About SPYDER OAuth Launcher")

        # Launch Mode Selection Frame
        mode_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        mode_frame.pack(fill=tk.X, pady=(0, 20))

        # Dashboard Only
        dashboard_frame = tk.Frame(mode_frame, bg=self.colors["bg"])
        dashboard_frame.pack(anchor=tk.W, pady=5)

        dashboard_rb = tk.Radiobutton(
            dashboard_frame,
            text="○  Dashboard Only – Visualization Mode",
            variable=self.launch_mode,
            value="dashboard",
            command=self.on_mode_change,
            font=("Arial", 12),
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["frame_bg"],
            activebackground=self.colors["bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        dashboard_rb.pack(anchor=tk.W)
        ToolTip(dashboard_rb, TOOLTIPS["dashboard"])

        # Paper Trading
        paper_frame = tk.Frame(mode_frame, bg=self.colors["bg"])
        paper_frame.pack(anchor=tk.W, pady=5)

        paper_rb = tk.Radiobutton(
            paper_frame,
            text="○  IBKR Web API – Paper Trading (OAuth 2.0)",
            variable=self.launch_mode,
            value="paper",
            command=self.on_mode_change,
            font=("Arial", 12),
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["frame_bg"],
            activebackground=self.colors["bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        paper_rb.pack(side=tk.LEFT, anchor=tk.W)
        ToolTip(paper_rb, TOOLTIPS["paper"])

        # OAuth configuration frame for Paper Trading (initially hidden)
        self.paper_oauth_frame = tk.Frame(mode_frame, bg=self.colors["frame_bg"])

        paper_oauth_inner = tk.Frame(self.paper_oauth_frame, bg=self.colors["frame_bg"])
        paper_oauth_inner.pack(padx=30, pady=10)

        # Client ID
        tk.Label(
            paper_oauth_inner,
            text="CLIENT ID",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)

        self.paper_client_id_entry = tk.Entry(
            paper_oauth_inner,
            textvariable=self.paper_client_id,
            font=("Arial", 11),
            bg=self.colors["input_bg"],
            fg=self.colors["fg"],
            insertbackground=self.colors["fg"],
            width=35,
        )
        self.paper_client_id_entry.grid(row=0, column=1, padx=(15, 5), pady=5)
        ToolTip(self.paper_client_id_entry, TOOLTIPS["client_id"])

        # Account ID
        tk.Label(
            paper_oauth_inner,
            text="ACCOUNT ID",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)

        self.paper_account_id_entry = tk.Entry(
            paper_oauth_inner,
            textvariable=self.paper_account_id,
            font=("Arial", 11),
            bg=self.colors["input_bg"],
            fg=self.colors["fg"],
            insertbackground=self.colors["fg"],
            width=35,
        )
        self.paper_account_id_entry.grid(row=1, column=1, padx=(15, 5), pady=5)
        ToolTip(self.paper_account_id_entry, TOOLTIPS["account_id"])

        # Private Key
        tk.Label(
            paper_oauth_inner,
            text="PRIVATE KEY",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)

        paper_key_frame = tk.Frame(paper_oauth_inner, bg=self.colors["frame_bg"])
        paper_key_frame.grid(row=2, column=1, padx=(15, 5), pady=5, sticky=tk.W + tk.E)

        self.paper_private_key_entry = tk.Entry(
            paper_key_frame,
            textvariable=self.paper_private_key,
            font=("Arial", 10),
            bg=self.colors["input_bg"],
            fg=self.colors["fg"],
            insertbackground=self.colors["fg"],
            width=30,
        )
        self.paper_private_key_entry.pack(side=tk.LEFT)
        ToolTip(self.paper_private_key_entry, TOOLTIPS["private_key"])

        paper_browse_btn = tk.Button(
            paper_key_frame,
            text="Browse",
            font=("Arial", 9),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            activebackground=self.colors["accent"],
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._browse_private_key("paper"),
        )
        paper_browse_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Environment
        tk.Label(
            paper_oauth_inner,
            text="ENVIRONMENT",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)

        paper_env_frame = tk.Frame(paper_oauth_inner, bg=self.colors["frame_bg"])
        paper_env_frame.grid(row=3, column=1, padx=(15, 5), pady=5, sticky=tk.W)

        paper_env_rb1 = tk.Radiobutton(
            paper_env_frame,
            text="Paper",
            variable=self.paper_environment,
            value="paper",
            font=("Arial", 10),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["input_bg"],
            activebackground=self.colors["frame_bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        paper_env_rb1.pack(side=tk.LEFT)

        paper_env_rb2 = tk.Radiobutton(
            paper_env_frame,
            text="Live",
            variable=self.paper_environment,
            value="live",
            font=("Arial", 10),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["input_bg"],
            activebackground=self.colors["frame_bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        paper_env_rb2.pack(side=tk.LEFT, padx=(15, 0))
        ToolTip(paper_env_frame, TOOLTIPS["environment"])

        # Remember configuration checkbox for Paper
        self.paper_remember_cb = tk.Checkbutton(
            paper_oauth_inner,
            text="Remember configuration",
            variable=self.save_paper_config,
            font=("Arial", 10),
            bg=self.colors["frame_bg"],
            fg=self.colors["accent"],
            selectcolor=self.colors["input_bg"],
            activebackground=self.colors["frame_bg"],
            activeforeground=self.colors["accent"],
        )
        self.paper_remember_cb.grid(
            row=4, column=0, columnspan=2, pady=(8, 0), sticky=tk.W, padx=5
        )
        ToolTip(
            self.paper_remember_cb,
            "Save configuration for next session\n(Private key path is not saved for security)",
        )

        # CONNECT button for Paper Trading
        self.paper_connect_btn = tk.Button(
            paper_oauth_inner,
            text="CONNECT",
            font=("Arial", 12, "bold"),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            activebackground=self.colors["accent"],
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._connect_to_ibkr("paper"),
            width=45,
            height=2,
        )
        self.paper_connect_btn.grid(row=5, column=0, columnspan=2, pady=(12, 8))
        ToolTip(self.paper_connect_btn, "Click to test OAuth authentication with IBKR")

        # Live Trading
        live_frame = tk.Frame(mode_frame, bg=self.colors["bg"])
        live_frame.pack(anchor=tk.W, pady=5)

        live_rb = tk.Radiobutton(
            live_frame,
            text="○  IBKR Web API – Live Trading (OAuth 2.0)",
            variable=self.launch_mode,
            value="live",
            command=self.on_mode_change,
            font=("Arial", 12),
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["frame_bg"],
            activebackground=self.colors["bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        live_rb.pack(side=tk.LEFT, anchor=tk.W)
        ToolTip(live_rb, TOOLTIPS["live"])

        # OAuth configuration frame for Live Trading (initially hidden)
        self.live_oauth_frame = tk.Frame(mode_frame, bg=self.colors["frame_bg"])

        live_oauth_inner = tk.Frame(self.live_oauth_frame, bg=self.colors["frame_bg"])
        live_oauth_inner.pack(padx=30, pady=10)

        # Client ID
        tk.Label(
            live_oauth_inner,
            text="CLIENT ID",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)

        self.live_client_id_entry = tk.Entry(
            live_oauth_inner,
            textvariable=self.live_client_id,
            font=("Arial", 11),
            bg=self.colors["input_bg"],
            fg=self.colors["fg"],
            insertbackground=self.colors["fg"],
            width=35,
        )
        self.live_client_id_entry.grid(row=0, column=1, padx=(15, 5), pady=5)
        ToolTip(self.live_client_id_entry, TOOLTIPS["client_id"])

        # Account ID
        tk.Label(
            live_oauth_inner,
            text="ACCOUNT ID",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)

        self.live_account_id_entry = tk.Entry(
            live_oauth_inner,
            textvariable=self.live_account_id,
            font=("Arial", 11),
            bg=self.colors["input_bg"],
            fg=self.colors["fg"],
            insertbackground=self.colors["fg"],
            width=35,
        )
        self.live_account_id_entry.grid(row=1, column=1, padx=(15, 5), pady=5)
        ToolTip(self.live_account_id_entry, TOOLTIPS["account_id"])

        # Private Key
        tk.Label(
            live_oauth_inner,
            text="PRIVATE KEY",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)

        live_key_frame = tk.Frame(live_oauth_inner, bg=self.colors["frame_bg"])
        live_key_frame.grid(row=2, column=1, padx=(15, 5), pady=5, sticky=tk.W + tk.E)

        self.live_private_key_entry = tk.Entry(
            live_key_frame,
            textvariable=self.live_private_key,
            font=("Arial", 10),
            bg=self.colors["input_bg"],
            fg=self.colors["fg"],
            insertbackground=self.colors["fg"],
            width=30,
        )
        self.live_private_key_entry.pack(side=tk.LEFT)
        ToolTip(self.live_private_key_entry, TOOLTIPS["private_key"])

        live_browse_btn = tk.Button(
            live_key_frame,
            text="Browse",
            font=("Arial", 9),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            activebackground=self.colors["accent"],
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._browse_private_key("live"),
        )
        live_browse_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Environment
        tk.Label(
            live_oauth_inner,
            text="ENVIRONMENT",
            font=("Arial", 11),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
        ).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)

        live_env_frame = tk.Frame(live_oauth_inner, bg=self.colors["frame_bg"])
        live_env_frame.grid(row=3, column=1, padx=(15, 5), pady=5, sticky=tk.W)

        live_env_rb1 = tk.Radiobutton(
            live_env_frame,
            text="Paper",
            variable=self.live_environment,
            value="paper",
            font=("Arial", 10),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["input_bg"],
            activebackground=self.colors["frame_bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        live_env_rb1.pack(side=tk.LEFT)

        live_env_rb2 = tk.Radiobutton(
            live_env_frame,
            text="Live",
            variable=self.live_environment,
            value="live",
            font=("Arial", 10),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
            selectcolor=self.colors["input_bg"],
            activebackground=self.colors["frame_bg"],
            activeforeground=self.colors["accent"],
            highlightthickness=0,
        )
        live_env_rb2.pack(side=tk.LEFT, padx=(15, 0))
        ToolTip(live_env_frame, TOOLTIPS["environment"])

        # Remember configuration checkbox for Live
        self.live_remember_cb = tk.Checkbutton(
            live_oauth_inner,
            text="Remember configuration",
            variable=self.save_live_config,
            font=("Arial", 10),
            bg=self.colors["frame_bg"],
            fg=self.colors["accent"],
            selectcolor=self.colors["input_bg"],
            activebackground=self.colors["frame_bg"],
            activeforeground=self.colors["accent"],
        )
        self.live_remember_cb.grid(
            row=4, column=0, columnspan=2, pady=(8, 0), sticky=tk.W, padx=5
        )
        ToolTip(
            self.live_remember_cb,
            "Save configuration for next session\n(Private key path is not saved for security)",
        )

        # CONNECT button for Live Trading
        self.live_connect_btn = tk.Button(
            live_oauth_inner,
            text="CONNECT",
            font=("Arial", 12, "bold"),
            bg=self.colors["input_bg"],
            fg=self.colors["accent"],
            activebackground=self.colors["accent"],
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._connect_to_ibkr("live"),
            width=45,
            height=2,
        )
        self.live_connect_btn.grid(row=5, column=0, columnspan=2, pady=(12, 8))
        ToolTip(self.live_connect_btn, "Click to test OAuth authentication with IBKR")

        # Launch Button (initially disabled)
        self.launch_btn = tk.Button(
            main_frame,
            text="🚀 LAUNCH",
            font=("Arial", 14, "bold"),
            bg=self.colors["accent"],
            fg="#000000",
            activebackground="#00dd77",
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.launch_system,
            state=tk.DISABLED,  # Initially disabled
            width=20,
            height=2,
        )
        self.launch_btn.pack(pady=25)

        # Initial state
        self.on_mode_change()

    def on_mode_change(self) -> None:
        """Handle launch mode change"""
        mode = self.launch_mode.get()

        # Hide all OAuth frames
        self.paper_oauth_frame.pack_forget()
        self.live_oauth_frame.pack_forget()

        # Show OAuth configuration for paper or live trading
        if mode == "paper":
            self.paper_oauth_frame.pack(anchor=tk.W, padx=30, pady=(5, 10))
            # Disable launch button until connected
            self.launch_btn.config(state=tk.DISABLED, bg="#666666", cursor="")
        elif mode == "live":
            self.live_oauth_frame.pack(anchor=tk.W, padx=30, pady=(5, 10))
            # Disable launch button until connected
            self.launch_btn.config(state=tk.DISABLED, bg="#666666", cursor="")
        else:
            # Dashboard mode - enable launch button (no connection needed)
            self.launch_btn.config(
                state=tk.NORMAL, bg=self.colors["accent"], cursor="hand2"
            )

    def _browse_private_key(self, mode: str) -> None:
        """Browse for private key file"""
        file_path = filedialog.askopenfilename(
            title="Select Private Key File",
            filetypes=[("PEM files", "*.pem"), ("All files", "*.*")],
        )

        if file_path:
            if mode == "paper":
                self.paper_private_key.set(file_path)
            else:
                self.live_private_key.set(file_path)

    def _connect_to_ibkr(self, mode: str) -> None:
        """
        Handle CONNECT button click - validates OAuth configuration and tests connection

        Args:
            mode: Either "paper" or "live"
        """
        # Get OAuth configuration based on mode
        if mode == "paper":
            client_id = self.paper_client_id.get().strip()
            account_id = self.paper_account_id.get().strip()
            private_key = self.paper_private_key.get().strip()
            environment = self.paper_environment.get().strip()
        else:  # live
            client_id = self.live_client_id.get().strip()
            account_id = self.live_account_id.get().strip()
            private_key = self.live_private_key.get().strip()
            environment = self.live_environment.get().strip()

        # Validate OAuth configuration
        is_valid, error_message = self.oauth_manager.validate_configuration(
            client_id, account_id, private_key, environment
        )

        if not is_valid:
            messagebox.showerror(
                "Invalid Configuration",
                f"OAuth configuration validation failed:\n\n{error_message}\n\n"
                "Please correct the configuration and try again.",
            )
            return

        self.logger.info(
            "Attempting to connect to IBKR %s Trading via OAuth...", mode.title()
        )

        # Disable CONNECT button during connection attempt
        if mode == "paper":
            self.paper_connect_btn.config(
                state=tk.DISABLED, text="CONNECTING...", bg=self.colors["input_bg"]
            )
        else:
            self.live_connect_btn.config(
                state=tk.DISABLED, text="CONNECTING...", bg=self.colors["input_bg"]
            )

        # Run connection check in background
        def connect():
            """Background thread for OAuth connection"""
            try:
                # Get access token using OAuth
                access_token = self.oauth_manager.get_access_token(
                    client_id, private_key, environment
                )

                if access_token:
                    self.connection_status = "connected"
                    self.logger.info(
                        "✅ Successfully connected to IBKR %s Trading via OAuth",
                        mode.title(),
                    )

                    # Enable launch button on main thread
                    self.root.after(0, self._enable_launch_button)

                    # Update CONNECT button with success state
                    if mode == "paper":
                        self.root.after(
                            0,
                            lambda: self.paper_connect_btn.config(
                                state=tk.NORMAL,
                                text="CONNECTED ✓",
                                bg=self.colors["accent"],
                                fg="#000000",
                                activeforeground="#000000",
                            ),
                        )
                    else:
                        self.root.after(
                            0,
                            lambda: self.live_connect_btn.config(
                                state=tk.NORMAL,
                                text="CONNECTED ✓",
                                bg=self.colors["accent"],
                                fg="#000000",
                                activeforeground="#000000",
                            ),
                        )

                    # Format expiration time safely
                    expiry_time = ""
                    if self.oauth_manager.token_expires_at:
                        expiry_time = self.oauth_manager.token_expires_at.strftime(
                            "%H:%M:%S"
                        )

                    # Show success message
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Connection Successful",
                            f"✓ Successfully connected to IBKR {mode.title()} Trading via OAuth!\n\n"
                            f"Access token expires at: {expiry_time}\n\n"
                            "You can now click LAUNCH to start the system.",
                        ),
                    )
                else:
                    # Connection failed
                    self.connection_status = "error"
                    self.logger.error(
                        "❌ Failed to connect to IBKR %s Trading via OAuth",
                        mode.title(),
                    )

                    # Re-enable CONNECT button
                    if mode == "paper":
                        self.root.after(
                            0,
                            lambda: self.paper_connect_btn.config(
                                state=tk.NORMAL,
                                text="CONNECT",
                                bg=self.colors["input_bg"],
                            ),
                        )
                    else:
                        self.root.after(
                            0,
                            lambda: self.live_connect_btn.config(
                                state=tk.NORMAL,
                                text="CONNECT",
                                bg=self.colors["input_bg"],
                            ),
                        )

                    # Show error message
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Connection Failed",
                            f"❌ Failed to connect to IBKR {mode.title()} Trading via OAuth\n\n"
                            "Please check:\n"
                            "• Your Client ID is correct\n"
                            "• Your Account ID is correct\n"
                            "• Private key file is valid\n"
                            "• Environment matches your account type\n"
                            "• Network connection is stable\n"
                            "• IBKR API services are available",
                        ),
                    )

            except (OSError, ValueError) as err:
                self.logger.error("OAuth connection error: %s", err)
                self.connection_status = "error"

                # Re-enable CONNECT button
                if mode == "paper":
                    self.root.after(
                        0,
                        lambda: self.paper_connect_btn.config(
                            state=tk.NORMAL, text="CONNECT", bg=self.colors["input_bg"]
                        ),
                    )
                else:
                    self.root.after(
                        0,
                        lambda: self.live_connect_btn.config(
                            state=tk.NORMAL, text="CONNECT", bg=self.colors["input_bg"]
                        ),
                    )

                error_msg = str(err)
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Connection Error",
                        f"❌ OAuth Connection Error\n\n"
                        f"An error occurred during OAuth authentication:\n\n"
                        f"{error_msg}\n\n"
                        "Troubleshooting:\n"
                        "• Check the logs for details\n"
                        "• Verify your OAuth configuration\n"
                        "• Ensure private key file is valid\n"
                        "• Contact support if issue persists",
                    ),
                )

        # Start connection thread
        connection_thread = threading.Thread(target=connect, daemon=True)
        connection_thread.start()

    def _enable_launch_button(self) -> None:
        """Enable the launch button after successful connection"""
        self.launch_btn.config(
            state=tk.NORMAL, bg=self.colors["accent"], cursor="hand2"
        )
        self.logger.info("Launch button enabled")

    def show_about(self) -> None:
        """Show About dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About SPYDER OAuth Launcher")
        about_window.geometry("450x400")
        about_window.resizable(False, False)
        about_window.configure(bg=self.colors["bg"])

        # Center on parent
        about_window.transient(self.root)
        about_window.grab_set()

        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        about_window.geometry(f"+{x}+{y}")

        # Content frame
        content = tk.Frame(about_window, bg=self.colors["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Logo/Title
        tk.Label(
            content,
            text="🕷️",
            font=("Arial", 48),
            bg=self.colors["bg"],
            fg=self.colors["accent"],
        ).pack(pady=(0, 10))

        tk.Label(
            content,
            text="SPYDER Trading System",
            font=("Arial", 16, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["accent"],
        ).pack()

        tk.Label(
            content,
            text="Autonomous Options Trading Platform",
            font=("Arial", 10),
            bg=self.colors["bg"],
            fg=self.colors["fg"],
        ).pack(pady=(0, 20))

        # Version info
        info_frame = tk.Frame(content, bg=self.colors["frame_bg"])
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = f"""
Version: {VERSION}
Build Date: {BUILD_DATE}
Author: Mohamed Talib

OAuth Launcher Features:
• OAuth 2.0 with JWT authentication
• Private key-based client authentication
• Paper & Live trading modes
• Access token management
• Automatic token refresh
• Secure configuration storage
• Session timeout protection
        """.strip()

        tk.Label(
            info_frame,
            text=info_text,
            font=("Arial", 9),
            bg=self.colors["frame_bg"],
            fg=self.colors["fg"],
            justify=tk.LEFT,
        ).pack(padx=15, pady=15)

        # Close button
        tk.Button(
            content,
            text="Close",
            font=("Arial", 10),
            bg=self.colors["accent"],
            fg="#000000",
            activebackground="#00dd77",
            relief=tk.FLAT,
            cursor="hand2",
            command=about_window.destroy,
        ).pack()

    def launch_system(self) -> None:
        """Launch the SPYDER system based on selected mode"""
        mode = self.launch_mode.get()

        self.logger.info("Launching SPYDER in %s mode", mode)

        # For trading modes, verify connection was established
        if mode in ["paper", "live"]:
            if self.connection_status != "connected":
                messagebox.showwarning(
                    "Connection Required",
                    "Please click CONNECT button first to establish OAuth connection.\n\n"
                    "The LAUNCH button will be enabled after successful connection.",
                )
                return

        # Save last mode
        self.config.set("SPYDER", "last_mode", mode)

        # Update session timestamp
        self.config.set("SPYDER", "last_session_check", datetime.now().isoformat())

        if mode == "dashboard":
            self._launch_dashboard_only()
        elif mode == "paper":
            # Save OAuth configuration if requested
            if self.save_paper_config.get():
                self.config.set(
                    "SPYDER", "remember_paper_client_id", self.paper_client_id.get()
                )
                self.config.set(
                    "SPYDER", "remember_paper_account_id", self.paper_account_id.get()
                )
                # Don't save private key path for security
                self.config.set(
                    "SPYDER", "remember_paper_environment", self.paper_environment.get()
                )
                self.config.set("SPYDER", "save_paper_config", "true")
            else:
                self.config.set("SPYDER", "remember_paper_client_id", "")
                self.config.set("SPYDER", "remember_paper_account_id", "")
                self.config.set("SPYDER", "remember_paper_environment", "paper")
                self.config.set("SPYDER", "save_paper_config", "false")

            self._launch_paper_trading()
        elif mode == "live":
            # Save OAuth configuration if requested
            if self.save_live_config.get():
                self.config.set(
                    "SPYDER", "remember_live_client_id", self.live_client_id.get()
                )
                self.config.set(
                    "SPYDER", "remember_live_account_id", self.live_account_id.get()
                )
                # Don't save private key path for security
                self.config.set(
                    "SPYDER", "remember_live_environment", self.live_environment.get()
                )
                self.config.set("SPYDER", "save_live_config", "true")
            else:
                self.config.set("SPYDER", "remember_live_client_id", "")
                self.config.set("SPYDER", "remember_live_account_id", "")
                self.config.set("SPYDER", "remember_live_environment", "live")
                self.config.set("SPYDER", "save_live_config", "false")

            self._launch_live_trading()

        # Save configuration
        self._save_configuration()

    def _launch_dashboard_only(self) -> None:
        """Launch dashboard in visualization mode only"""
        try:
            self.logger.info("Launching Dashboard Only mode")

            # Find dashboard executable
            dashboard_path = (
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py"
            )

            if not dashboard_path.exists():
                messagebox.showerror(
                    "Error", f"Dashboard not found at:\n{dashboard_path}"
                )
                return

            # Launch dashboard without IBKR connection
            subprocess.Popen(
                [sys.executable, str(dashboard_path), "--mode", "visualization"]
            )

            self.logger.info("✅ Dashboard launched successfully")

            # Show success message before closing
            messagebox.showinfo(
                "Success",
                "Dashboard launched in visualization mode.\n\n"
                "No IBKR connection - simulated data only.",
            )

            # Close launcher after showing message
            self.close_launcher()

        except (OSError, subprocess.SubprocessError) as err:
            self.logger.error("Dashboard launch failed: %s", err)
            messagebox.showerror("Error", f"Failed to launch dashboard:\n{err}")

    def _launch_paper_trading(self) -> None:
        """Launch system with IBKR Web API in Paper Trading mode"""
        client_id = self.paper_client_id.get().strip()
        account_id = self.paper_account_id.get().strip()
        private_key = self.paper_private_key.get().strip()
        environment = self.paper_environment.get().strip()

        # Validate configuration
        is_valid, error_message = self.oauth_manager.validate_configuration(
            client_id, account_id, private_key, environment
        )

        if not is_valid:
            messagebox.showwarning(
                "Invalid Configuration",
                f"OAuth configuration validation failed:\n\n{error_message}",
            )
            return

        try:
            self.logger.info("Launching Paper Trading mode with IBKR Web API OAuth")

            # Find main system launcher
            main_launcher = (
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py"
            )

            # Debug logging
            self.logger.info(f"SPYDER_HOME: {SPYDER_HOME}")
            self.logger.info(f"Looking for dashboard at: {main_launcher}")
            self.logger.info(f"Dashboard exists: {main_launcher.exists()}")
            self.logger.info(f"Absolute path: {main_launcher.absolute()}")

            if not main_launcher.exists():
                messagebox.showerror(
                    "Error", f"Main system not found at:\n{main_launcher}"
                )
                return

            # Launch with paper trading mode
            subprocess.Popen(
                [
                    sys.executable,
                    str(main_launcher),
                    "--mode",
                    "paper",
                    "--client_id",
                    client_id,
                    "--account_id",
                    account_id,
                    "--private_key",
                    private_key,
                    "--environment",
                    environment,
                    "--api",
                    "oauth",
                ]
            )

            self.logger.info("✅ Paper trading mode launched with OAuth")

            # Show success message before closing
            messagebox.showinfo(
                "Success",
                "SPYDER launching with IBKR Web API (Paper Trading) via OAuth.\n\n"
                "Access token will be automatically managed and refreshed.",
            )

            # Close launcher after showing message
            self.close_launcher()

        except (OSError, subprocess.SubprocessError) as err:
            self.logger.error("Paper trading launch failed: %s", err)
            messagebox.showerror("Error", f"Failed to launch paper trading:\n{err}")

    def _launch_live_trading(self) -> None:
        """Launch system with IBKR Web API in Live Trading mode"""
        client_id = self.live_client_id.get().strip()
        account_id = self.live_account_id.get().strip()
        private_key = self.live_private_key.get().strip()
        environment = self.live_environment.get().strip()

        # Validate configuration
        is_valid, error_message = self.oauth_manager.validate_configuration(
            client_id, account_id, private_key, environment
        )

        if not is_valid:
            messagebox.showwarning(
                "Invalid Configuration",
                f"OAuth configuration validation failed:\n\n{error_message}",
            )
            return

        # Confirm live trading
        confirm = messagebox.askyesno(
            "⚠️ Live Trading Confirmation",
            "You are about to launch LIVE TRADING mode.\n\n"
            "This will use REAL MONEY.\n\n"
            "Are you sure you want to proceed?",
            icon="warning",
        )

        if not confirm:
            return

        try:
            self.logger.info("Launching Live Trading mode with IBKR Web API OAuth")

            # Find main system launcher
            main_launcher = (
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py"
            )

            # Debug logging
            self.logger.info(f"SPYDER_HOME: {SPYDER_HOME}")
            self.logger.info(f"Looking for dashboard at: {main_launcher}")
            self.logger.info(f"Dashboard exists: {main_launcher.exists()}")
            self.logger.info(f"Absolute path: {main_launcher.absolute()}")

            if not main_launcher.exists():
                messagebox.showerror(
                    "Error", f"Main system not found at:\n{main_launcher}"
                )
                return

            # Launch with live trading mode
            subprocess.Popen(
                [
                    sys.executable,
                    str(main_launcher),
                    "--mode",
                    "live",
                    "--client_id",
                    client_id,
                    "--account_id",
                    account_id,
                    "--private_key",
                    private_key,
                    "--environment",
                    environment,
                    "--api",
                    "oauth",
                ]
            )

            self.logger.info("✅ Live trading mode launched with OAuth")

            # Show success message before closing
            messagebox.showinfo(
                "Success",
                "SPYDER launching with IBKR Web API (LIVE TRADING) via OAuth.\n\n"
                "⚠️ REAL MONEY MODE ACTIVATED ⚠️\n\n"
                "Access token will be automatically managed and refreshed.",
            )

            # Close launcher after showing message
            self.close_launcher()

        except (OSError, subprocess.SubprocessError) as err:
            self.logger.error("Live trading launch failed: %s", err)
            messagebox.showerror("Error", f"Failed to launch live trading:\n{err}")

    def close_launcher(self) -> None:
        """Close the launcher window"""
        self.root.after(500, self.root.destroy)

    def on_closing(self) -> None:
        """Handle window close event"""
        self.logger.info("OAuth launcher closed by user")
        self.root.destroy()

    def run(self) -> None:
        """Run the launcher main loop"""
        self.logger.info("Starting OAuth launcher GUI")
        self.root.mainloop()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point for the OAuth launcher"""
    try:
        launcher = SpyderOAuthLauncher()
        launcher.run()
    except (KeyboardInterrupt, SystemExit):
        print("\nLauncher closed by user")
        sys.exit(0)
    except Exception as fatal_err:
        print(f"FATAL ERROR: {fatal_err}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
