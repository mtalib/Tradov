#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_StreamlinedLauncher.py
Purpose: Streamlined GUI launcher with dashboard-first workflow

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-24 Time: 12:00:00
Version: 3.0.0

Module Description:
    Revolutionary launcher design where the dashboard launches FIRST, then IBKR
    login opens in browser. This provides superior user experience by:
    - Dashboard visible immediately (no waiting)
    - Real-time connection status visible on dashboard
    - User can see progress while logging in
    - Dashboard polls for IBKR connection and switches modes automatically
    - More professional and polished workflow

    The launcher now has only 2 simple options:
    1. Launch Dashboard Only (simulation mode)
    2. Launch Dashboard & IBKR Web API Login (dashboard opens, then browser for login)

Module Constants:
    VERSION (str): Current module version (default: "3.0.0")
    BUILD_DATE (str): Build date in YYYY-MM-DD format (default: "2025-10-24")
    SPYDER_HOME (Path): Main Spyder project directory (default: ~/Projects/Spyder)
    CONFIG_DIR (Path): Configuration directory (default: ~/Projects/Spyder/config)
    CONFIG_FILE (Path): Launcher configuration file (default: launcher_config_v3.ini)
    LOG_DIR (Path): Log directory (default: ~/spyder_logs)

Change Log:
    2025-10-24 (v3.0.0):
        - Revolutionary workflow: Dashboard launches FIRST, then IBKR login
        - Simplified to 2 options: "Dashboard Only" or "Dashboard & IBKR"
        - Removed authentication polling from launcher (dashboard handles it)
        - Launcher now just launches and exits immediately
        - Dashboard handles IBKR connection detection and mode switching
        - Much better user experience - no dead time waiting
        - Cleaner separation of concerns

    2025-10-23 (v2.1.0):
        - Removed redundant Paper/Live radio buttons from launcher
        - Simplified to single "IBKR Web API – Connect & Trade" option
        - User chooses Paper/Live on IBKR login page

    2025-10-23 (v2.0.0):
        - Combined CONNECT + LAUNCH into one action
        - Removed unnecessary success dialogs

    2025-10-15 (v1.0.0):
        - Initial module creation

Dependencies:
    - tkinter for GUI
    - SpyderU_Utilities for logging
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import subprocess
import configparser
import webbrowser
from pathlib import Path
from typing import Optional
from datetime import datetime

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
VERSION = "3.0.0"
BUILD_DATE = "2025-10-24"

SPYDER_HOME = Path.home() / "Projects" / "Spyder"
CONFIG_DIR = SPYDER_HOME / "config"
CONFIG_FILE = CONFIG_DIR / "launcher_config_v3.ini"
LOG_DIR = Path.home() / "spyder_logs"

# Tooltips with clear messaging
TOOLTIPS = {
    "dashboard_only": "Launch dashboard in simulation mode.\n"
    "• No IBKR connection\n"
    "• Uses simulated market data\n"
    "• Safe for learning and testing\n"
    "• Immediate launch",
    "dashboard_ibkr": "Launch dashboard, then open IBKR login.\n"
    "• Dashboard opens IMMEDIATELY\n"
    "• Browser opens for IBKR authentication\n"
    "• Dashboard shows connection status in real-time\n"
    "• You choose Paper or Live on IBKR login page\n"
    "• Dashboard automatically switches to live data when connected\n\n"
    "Flow: Click LAUNCH → Dashboard opens → Browser opens → Login → Connected!",
}


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class StreamlinedSpyderLauncher:
    """
    Streamlined SPYDER launcher with dashboard-first workflow and direct button access.

    This launcher provides two dedicated buttons for instant launch:
    - LAUNCH DASHBOARD: Simulation mode only
    - LAUNCH DASHBOARD & IBKR LOGIN: Full IBKR integration

    The dashboard launches immediately in both modes. For IBKR mode, the gateway
    starts automatically and the browser opens for authentication while the dashboard
    is already visible showing connection status.

    Attributes:
        root: Tkinter root window
        logger: Module logger instance
        config: Configuration parser
        colors: UI color scheme dictionary
        status_label: Status bar label widget

    Example:
        >>> launcher = StreamlinedSpyderLauncher()
        >>> launcher.run()
    """

    def __init__(self):
        """Initialize the streamlined launcher."""
        self.root = tk.Tk()
        self.root.title("SPYDER Launcher v3.0")
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        # Setup logging
        self.logger = get_logger(__name__)
        self.logger.info("Initializing StreamlinedSpyderLauncher v3.0")

        # Load configuration
        self.config = configparser.ConfigParser()
        self._load_configuration()

        # Dark theme colors
        self.colors = {
            "bg": "#1a1a2e",
            "fg": "#eee",
            "button": "#16213e",
            "accent": "#0f3460",
            "status_bg": "#0f1419",
            "text_dim": "#6c757d",
            "green": "#00ff88",
        }

        # Setup UI
        self._setup_ui()

        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.logger.info("StreamlinedSpyderLauncher initialized")

    # ==========================================================================
    # CONFIGURATION METHODS
    # ==========================================================================

    def _load_configuration(self):
        """Load launcher configuration from file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            if CONFIG_FILE.exists():
                self.config.read(CONFIG_FILE)
                self.logger.info(f"Configuration loaded from {CONFIG_FILE}")
            else:
                # Create default configuration
                self.config["SPYDER"] = {"last_mode": "dashboard_only"}
                self._save_configuration()
                self.logger.info("Created default configuration")

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.config["SPYDER"] = {"last_mode": "dashboard_only"}

    def _save_configuration(self):
        """Save launcher configuration to file."""
        try:
            with open(CONFIG_FILE, "w") as f:
                self.config.write(f)
            self.logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")

    # ==========================================================================
    # UI SETUP METHODS
    # ==========================================================================

    def _setup_ui(self):
        """Set up the launcher UI."""
        self.root.configure(bg=self.colors["bg"])

        # Main frame
        main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # Header
        header_label = tk.Label(
            main_frame,
            text="🕷️ SPYDER AUTONOMOUS OPTIONS TRADING SYSTEM",
            font=("Arial", 14, "bold"),
            bg=self.colors["bg"],
            fg=self.colors["accent"],
        )
        header_label.pack(pady=(0, 30))

        # Info text
        info_text = (
            "Choose your launch mode:\n\n"
            "• Dashboard Only - Simulated data, no IBKR connection\n"
            "• Dashboard & IBKR Login - Live connection with Web API"
        )
        info_label = tk.Label(
            main_frame,
            text=info_text,
            font=("Arial", 10),
            bg=self.colors["bg"],
            fg=self.colors["fg"],
            justify="left",
        )
        info_label.pack(pady=(0, 30))

        # Launch buttons frame
        buttons_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        buttons_frame.pack(pady=20)

        # Button 1: Launch Dashboard Only
        dashboard_btn = tk.Button(
            buttons_frame,
            text="📊 LAUNCH DASHBOARD",
            font=("Arial", 12, "bold"),
            bg=self.colors["button"],
            fg=self.colors["fg"],
            activebackground=self.colors["accent"],
            activeforeground="#000",
            command=lambda: self.launch(mode="dashboard_only"),
            cursor="hand2",
            relief="flat",
            bd=0,
            padx=40,
            pady=20,
            width=30,
        )
        dashboard_btn.pack(pady=10)
        self._create_tooltip(dashboard_btn, TOOLTIPS["dashboard_only"])

        # Button 2: Launch Dashboard & IBKR
        dashboard_ibkr_btn = tk.Button(
            buttons_frame,
            text="� LAUNCH DASHBOARD & IBKR LOGIN",
            font=("Arial", 12, "bold"),
            bg=self.colors["green"],
            fg="#000",
            activebackground="#00dd00",
            activeforeground="#000",
            command=lambda: self.launch(mode="dashboard_ibkr"),
            cursor="hand2",
            relief="flat",
            bd=0,
            padx=40,
            pady=20,
            width=30,
        )
        dashboard_ibkr_btn.pack(pady=10)
        self._create_tooltip(dashboard_ibkr_btn, TOOLTIPS["dashboard_ibkr"])

        # Status bar
        status_frame = tk.Frame(main_frame, bg=self.colors["status_bg"], height=40)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            status_frame,
            text="Ready to launch",
            font=("Arial", 9),
            bg=self.colors["status_bg"],
            fg=self.colors["text_dim"],
            anchor="w",
        )
        self.status_label.pack(fill="both", padx=10, pady=8)

        # Help button
        help_btn = tk.Label(
            main_frame,
            text="?",
            font=("Arial", 10, "bold"),
            bg=self.colors["button"],
            fg=self.colors["fg"],
            cursor="hand2",
            width=3,
            height=1,
        )
        help_btn.place(relx=1.0, rely=0.0, x=-10, y=-10, anchor="ne")
        help_btn.bind("<Button-1>", lambda e: self.show_help())

    def _create_tooltip(self, widget, text):
        """
        Create tooltip for widget.

        Args:
            widget: Tkinter widget to attach tooltip to
            text: Tooltip text content
        """

        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = tk.Label(
                tooltip,
                text=text,
                justify="left",
                background=self.colors["button"],
                foreground=self.colors["fg"],
                relief="solid",
                borderwidth=1,
                font=("Arial", 9),
                padx=10,
                pady=10,
            )
            label.pack()

            def hide_tooltip():
                tooltip.destroy()

            widget.tooltip = tooltip
            widget.bind("<Leave>", lambda e: hide_tooltip())
            tooltip.bind("<Leave>", lambda e: hide_tooltip())

        widget.bind("<Enter>", show_tooltip)

    # ==========================================================================
    # GATEWAY DETECTION METHODS
    # ==========================================================================

    def _check_gateway_status(self) -> bool:
        """
        Check if IBKR Client Portal Gateway is running.

        Returns:
            bool: True if gateway detected, False otherwise
        """
        try:
            import requests
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            response = requests.get(
                "https://localhost:5000/v1/api/one/user", verify=False, timeout=2
            )
            return response.status_code in [
                200,
                401,
            ]  # 401 means gateway running but not authenticated

        except Exception:
            return False

    # ==========================================================================
    # LAUNCH METHODS
    # ==========================================================================

    def update_status(self, message: str):
        """
        Update status bar message.

        Args:
            message: Status message to display
        """
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def launch(self, mode: str):
        """
        Launch the dashboard with the specified mode.

        Args:
            mode: "dashboard_only" or "dashboard_ibkr"

        Launcher exits immediately after launching.
        """
        try:
            self.logger.info(f"Launch initiated - mode: {mode}")

            # Save preference
            self.config["SPYDER"]["last_mode"] = mode
            self._save_configuration()

            if mode == "dashboard_only":
                # Launch dashboard in simulation mode
                self.update_status("Launching dashboard...")
                self.launch_dashboard(with_ibkr=False)
                messagebox.showinfo(
                    "Dashboard Launched",
                    "Dashboard is now running in simulation mode!",
                )

                # Close launcher after brief delay
                time.sleep(1)
                self.logger.info("Launcher closing - dashboard launched")
                self.root.destroy()

            elif mode == "dashboard_ibkr":
                # NEW WORKFLOW: Launch dashboard first, then gateway
                self.update_status("Launching dashboard...")
                self.launch_dashboard(with_ibkr=True)

                # Launch gateway after dashboard (this waits for gateway to be ready)
                self.update_status("Starting IBKR Client Portal Gateway...")
                self.launch_gateway()

                # Gateway is ready (or timed out) - close launcher
                self.logger.info("Launcher closing - dashboard and gateway launched")
                self.root.destroy()

        except Exception as e:
            error_msg = f"Launch failed: {e}"
            self.logger.error(error_msg, exc_info=True)
            messagebox.showerror("Launch Error", error_msg)

    def launch_dashboard(self, with_ibkr: bool = False):
        """
        Launch the trading dashboard.

        The dashboard will:
        - Open immediately
        - If with_ibkr=True, open browser for login and poll for connection
        - Show connection status in real-time
        - Switch to live data when IBKR connects

        Args:
            with_ibkr: Whether to enable IBKR connection mode
        """
        try:
            dashboard_script = (
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py"
            )

            if not dashboard_script.exists():
                error_msg = f"Dashboard not found: {dashboard_script}"
                self.logger.error(error_msg)
                messagebox.showerror("Error", error_msg)
                return

            # Build command
            venv_python = SPYDER_HOME / ".venv" / "bin" / "python"
            if not venv_python.exists():
                venv_python = sys.executable

            cmd = [str(venv_python), str(dashboard_script)]

            if with_ibkr:
                # Dashboard will handle IBKR connection and browser launch
                cmd.extend(["--mode", "ibkr-connect"])
            else:
                # Pure simulation mode
                cmd.extend(["--mode", "simulation"])

            self.logger.info(f"Launching dashboard: {' '.join(cmd)}")

            # Launch dashboard
            subprocess.Popen(
                cmd,
                cwd=str(SPYDER_HOME),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            self.update_status("✅ Dashboard launched successfully")
            self.logger.info("Dashboard launched successfully")

        except Exception as e:
            error_msg = f"Failed to launch dashboard: {str(e)}"
            self.logger.error(error_msg)
            messagebox.showerror("Launch Error", error_msg)

    def launch_gateway(self):
        """
        Launch the IBKR Client Portal Gateway.

        This starts the gateway process which will:
        - Listen on port 5000
        - Open browser for IBKR authentication
        - Handle OAuth/session management

        The method waits for the gateway to be ready before opening the browser.
        """
        try:
            # First check if gateway is already running
            self.logger.info("Checking if gateway is already running...")
            if self._check_gateway_status():
                self.logger.info("✅ Gateway already running!")
                # Just open the browser
                login_url = "https://localhost:5000"
                self.logger.info(f"Opening browser to {login_url}")
                webbrowser.open(login_url)
                return

            # Gateway not running - need to start it
            gateway_script = SPYDER_HOME / "SpyderG_GUI" / "start_gateway.sh"

            if not gateway_script.exists():
                # Fallback: provide instructions
                self.logger.warning("Gateway script not found")
                messagebox.showwarning(
                    "Gateway Setup Required",
                    "IBKR Client Portal Gateway script not found.\n\n"
                    "Please set up the gateway using:\n"
                    "  cd SpyderG_GUI\n"
                    "  ./start_gateway.sh paper\n\n"
                    "See CLIENT_PORTAL_GATEWAY_SETUP.md for details.",
                )
                return

            # Start the gateway
            self.logger.info("Starting gateway using start_gateway.sh")
            self.update_status("Starting IBKR Gateway...")

            subprocess.Popen(
                ["bash", str(gateway_script), "paper"],  # Default to paper mode
                cwd=str(SPYDER_HOME / "SpyderG_GUI"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            # Wait for gateway to be ready (with timeout)
            self.logger.info("Waiting for gateway to be ready...")
            max_wait = 30  # 30 seconds max
            check_interval = 2  # Check every 2 seconds
            waited = 0

            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval

                self.update_status(f"Waiting for gateway... ({waited}s)")

                if self._check_gateway_status():
                    self.logger.info(f"✅ Gateway ready after {waited} seconds!")
                    self.update_status("Gateway ready! Opening browser...")

                    # Gateway is ready - open browser
                    login_url = "https://localhost:5000"
                    self.logger.info(f"Opening browser to {login_url}")
                    webbrowser.open(login_url)
                    self.logger.info("✅ Browser opened for IBKR authentication")
                    return

            # Timeout reached
            self.logger.warning(f"Gateway did not start within {max_wait} seconds")
            messagebox.showwarning(
                "Gateway Startup Slow",
                f"Gateway is taking longer than expected to start.\n\n"
                f"The browser will not open automatically.\n"
                f"Please wait a moment and then manually visit:\n"
                f"https://localhost:5000\n\n"
                f"To check gateway status:\n"
                f"  docker logs -f ibkr-gateway-paper"
            )

        except Exception as e:
            error_msg = f"Failed to launch gateway: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            # Don't show error popup - gateway is optional
            self.logger.warning(
                "Dashboard can still run without gateway (simulation mode)"
            )

    # ==========================================================================
    # HELP AND INFO METHODS
    # ==========================================================================

    def show_help(self):
        """Show help dialog."""
        help_text = (
            """🕷️ SPYDER LAUNCHER v3.0 HELP

REVOLUTIONARY WORKFLOW:
━━━━━━━━━━━━━━━━━━━━━━━━━━

The dashboard now launches FIRST, giving you immediate visual feedback!

LAUNCH OPTIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 LAUNCH DASHBOARD ONLY
• Dashboard opens with simulated data
• No IBKR connection
• Safe for learning and testing

💼 LAUNCH DASHBOARD & IBKR WEB API LOGIN
• Dashboard opens IMMEDIATELY
• Browser opens for IBKR authentication
• Dashboard shows "Connecting..." status
• You choose Paper or Live on IBKR login page
• Dashboard automatically detects connection
• Switches to live data when connected

WORKFLOW:
━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Click LAUNCH → Dashboard appears instantly
2. Browser opens to IBKR login page
3. Dashboard shows "Connecting to IBKR..."
4. You log in and choose Paper or Live
5. Dashboard detects connection automatically
6. Status updates to "✅ IBKR Connected - PAPER" or "LIVE"
7. Dashboard switches to real-time data

BENEFITS:
• No waiting - dashboard visible immediately
• See connection progress in real-time
• Professional user experience
• Dashboard in control of connection

PREREQUISITES:
• Client Portal Gateway running on port 5000
• Valid IBKR account credentials

Version: """
            + VERSION
            + """
Build: """
            + BUILD_DATE
        )

        messagebox.showinfo("SPYDER Launcher Help", help_text)

    def on_closing(self):
        """Handle window close event."""
        self.logger.info("Launcher window closed")
        self.root.destroy()

    def run(self):
        """Run the launcher."""
        self.logger.info("Starting launcher main loop")
        self.root.mainloop()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """
    Main entry point for launcher.

    Returns:
        int: Exit code (0 for success)
    """
    # Ensure log directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create and run launcher
    launcher = StreamlinedSpyderLauncher()
    launcher.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
