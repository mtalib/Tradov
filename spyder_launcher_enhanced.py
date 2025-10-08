#!/usr/bin/env python3
"""
SPYDER Enhanced Launcher with Remote TWS & Trading Mode Selection
Professional trading system launcher with complete configuration options

Features:
- Local IB Gateway vs Remote TWS selection
- Paper vs Live trading mode
- Smart detection and auto-configuration
- Nuclear restart capability
- Multi-environment support
"""

import os
import sys
import time
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import threading
import configparser
import re

# Paths and Configuration
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
JTS_PATH = Path.home() / "Jts"
CONFIG_FILE = SPYDER_HOME / "spyder_launcher_config.ini"
VENV_PYTHON = SPYDER_HOME / ".venv" / "bin" / "python3"

# Default Configuration
DEFAULT_CONFIG = {
    "connection_type": "local_gateway",  # local_gateway or remote_tws
    "trading_mode": "paper",  # paper or live
    "local_gateway_paper_port": "4002",
    "local_gateway_live_port": "4001",
    "remote_tws_host": "192.168.1.2",
    "remote_tws_paper_port": "7497",
    "remote_tws_live_port": "7496",
    "auto_launch_dashboard": "true",
}


def load_bashrc_credentials():
    """Load IB credentials from bashrc file"""
    bashrc_path = Path.home() / ".bashrc"
    credentials = {}

    if not bashrc_path.exists():
        print("Warning: .bashrc not found")
        return credentials

    try:
        with open(bashrc_path, "r") as f:
            content = f.read()

        # Extract credentials using regex
        patterns = {
            "IB_PAPER_USERNAME": r'export\s+IB_PAPER_USERNAME=["\']([^"\']+)["\']',
            "IB_PAPER_PASSWORD": r'export\s+IB_PAPER_PASSWORD=["\']([^"\']+)["\']',
            "IB_LIVE_USERNAME": r'export\s+IB_LIVE_USERNAME=["\']([^"\']+)["\']',
            "IB_LIVE_PASSWORD": r'export\s+IB_LIVE_PASSWORD=["\']([^"\']+)["\']',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                credentials[key] = match.group(1)
                # Also set in current environment
                os.environ[key] = match.group(1)

        if credentials:
            print(
                f"✅ Loaded credentials from .bashrc: {', '.join(credentials.keys())}"
            )
        else:
            print("⚠️ No IB credentials found in .bashrc")

    except Exception as e:
        print(f"Error loading .bashrc credentials: {e}")

    return credentials


class SpyderEnhancedLauncher:
    def __init__(self):
        # Load credentials from bashrc first
        self.credentials = load_bashrc_credentials()

        self.config = self.load_config()
        self.root = tk.Tk()
        self.setup_window()
        self.setup_styles()
        self.create_widgets()
        self.check_system_status()

    def load_config(self):
        """Load or create configuration"""
        config = configparser.ConfigParser()

        if CONFIG_FILE.exists():
            config.read(CONFIG_FILE)
            if "SPYDER" not in config:
                config["SPYDER"] = {}
            for key, default_value in DEFAULT_CONFIG.items():
                if key not in config["SPYDER"]:
                    config["SPYDER"][key] = default_value
        else:
            config["SPYDER"] = DEFAULT_CONFIG
            self.save_config(config)

        return config

    def save_config(self, config=None):
        """Save configuration to file"""
        if config is None:
            config = self.config

        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            config.write(f)

    def get_config_value(self, key):
        """Get configuration value"""
        return self.config["SPYDER"].get(key, DEFAULT_CONFIG.get(key, ""))

    def set_config_value(self, key, value):
        """Set configuration value"""
        self.config["SPYDER"][key] = value
        self.save_config()

    def setup_window(self):
        """Configure main window"""
        self.root.title("🕷️ SPYDER Enhanced Trading System")
        self.root.geometry("650x600")
        self.root.resizable(False, False)

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

    def setup_styles(self):
        """Configure UI styles"""
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Dark theme colors
        bg_color = "#2d2d2d"
        fg_color = "#ffffff"
        accent_color = "#00ff88"

        self.root.configure(bg=bg_color)

        self.style.configure(
            "Title.TLabel",
            font=("Arial", 16, "bold"),
            foreground=accent_color,
            background=bg_color,
        )

        self.style.configure(
            "Status.TLabel",
            font=("Arial", 10),
            foreground=fg_color,
            background=bg_color,
        )

    def create_widgets(self):
        """Create GUI components"""
        main_frame = tk.Frame(self.root, bg="#2d2d2d")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        ttk.Label(
            main_frame, text="🕷️ SPYDER TRADING SYSTEM", style="Title.TLabel"
        ).pack(pady=(0, 10))

        ttk.Label(
            main_frame,
            text="Enhanced Professional Trading Platform",
            style="Status.TLabel",
        ).pack(pady=(0, 20))

        # Configuration Frame
        config_frame = tk.LabelFrame(
            main_frame,
            text="Trading Configuration",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 11, "bold"),
        )
        config_frame.pack(fill=tk.X, pady=(0, 15))

        # Connection Type
        ttk.Label(config_frame, text="Connection Type:", style="Status.TLabel").pack(
            anchor=tk.W, padx=10, pady=(10, 5)
        )

        self.connection_type = tk.StringVar(
            value=self.get_config_value("connection_type")
        )

        conn_frame = tk.Frame(config_frame, bg="#2d2d2d")
        conn_frame.pack(anchor=tk.W, padx=20, pady=(0, 10))

        ttk.Radiobutton(
            conn_frame,
            text="🏠 Local IB Gateway",
            variable=self.connection_type,
            value="local_gateway",
            command=self.on_config_change,
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            conn_frame,
            text="🌐 Remote TWS (192.168.1.2)",
            variable=self.connection_type,
            value="remote_tws",
            command=self.on_config_change,
        ).pack(side=tk.LEFT)

        # Trading Mode
        ttk.Label(config_frame, text="Trading Mode:", style="Status.TLabel").pack(
            anchor=tk.W, padx=10, pady=(10, 5)
        )

        self.trading_mode = tk.StringVar(value=self.get_config_value("trading_mode"))

        mode_frame = tk.Frame(config_frame, bg="#2d2d2d")
        mode_frame.pack(anchor=tk.W, padx=20, pady=(0, 10))

        ttk.Radiobutton(
            mode_frame,
            text="📄 Paper Trading (Safe)",
            variable=self.trading_mode,
            value="paper",
            command=self.on_config_change,
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Radiobutton(
            mode_frame,
            text="🔴 LIVE Trading (Real Money)",
            variable=self.trading_mode,
            value="live",
            command=self.on_mode_change,
        ).pack(side=tk.LEFT)

        # Current Configuration Display
        self.config_display = ttk.Label(config_frame, text="", style="Status.TLabel")
        self.config_display.pack(padx=10, pady=(5, 15))
        self.update_config_display()

        # System Status Frame
        status_frame = tk.LabelFrame(
            main_frame,
            text="System Status",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        status_frame.pack(fill=tk.X, pady=(0, 15))

        self.connection_status = ttk.Label(
            status_frame, text="🔍 Checking connection...", style="Status.TLabel"
        )
        self.connection_status.pack(anchor=tk.W, padx=10, pady=5)

        self.api_status = ttk.Label(
            status_frame, text="🔍 Checking API...", style="Status.TLabel"
        )
        self.api_status.pack(anchor=tk.W, padx=10, pady=5)

        self.spyder_status = ttk.Label(
            status_frame, text="🔍 Checking SPYDER...", style="Status.TLabel"
        )
        self.spyder_status.pack(anchor=tk.W, padx=10, pady=5)

        # Launch Options Frame
        options_frame = tk.LabelFrame(
            main_frame,
            text="Launch Options",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Buttons in 2x2 grid
        button_frame = tk.Frame(options_frame, bg="#2d2d2d")
        button_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Smart Launch
        self.smart_btn = ttk.Button(
            button_frame, text="🚀 Smart Launch", command=self.smart_launch
        )
        self.smart_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))

        # Nuclear Restart
        self.restart_btn = ttk.Button(
            button_frame, text="🔥 Nuclear Restart", command=self.nuclear_restart
        )
        self.restart_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 5))

        # Test Connection
        self.test_btn = ttk.Button(
            button_frame, text="🧪 Test Connection", command=self.test_connection
        )
        self.test_btn.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(5, 0))

        # Dashboard Only
        self.dashboard_btn = ttk.Button(
            button_frame, text="📊 Dashboard Only", command=self.dashboard_only
        )
        self.dashboard_btn.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(5, 0))

        # Configure grid weights
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Bottom buttons
        bottom_frame = tk.Frame(main_frame, bg="#2d2d2d")
        bottom_frame.pack(fill=tk.X)

        ttk.Button(bottom_frame, text="🔄 Switch Mode", command=self.quick_switch).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        ttk.Button(bottom_frame, text="⚙️ Settings", command=self.show_settings).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        ttk.Button(
            bottom_frame, text="🔄 Refresh", command=self.check_system_status
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(bottom_frame, text="❓ Help", command=self.show_help).pack(
            side=tk.LEFT
        )

        ttk.Button(bottom_frame, text="❌ Exit", command=self.root.quit).pack(
            side=tk.RIGHT
        )

        # Progress bar (initially hidden)
        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")
        self.progress_label = ttk.Label(main_frame, text="", style="Status.TLabel")

    def on_config_change(self):
        """Handle configuration changes"""
        self.set_config_value("connection_type", self.connection_type.get())
        self.set_config_value("trading_mode", self.trading_mode.get())
        self.update_config_display()
        self.check_system_status()

    def on_mode_change(self):
        """Handle trading mode change with confirmation"""
        mode = self.trading_mode.get()

        if mode == "live":
            result = messagebox.askyesno(
                "⚠️ LIVE Trading Mode",
                "🔴 WARNING: You have selected LIVE TRADING mode!\n\n"
                "This will use REAL MONEY for trading.\n\n"
                "Are you absolutely sure you want to proceed?",
                icon="warning",
            )
            if not result:
                self.trading_mode.set("paper")
                return

        self.on_config_change()

    def update_config_display(self):
        """Update configuration display"""
        conn_type = self.connection_type.get()
        mode = self.trading_mode.get()

        if conn_type == "local_gateway":
            host = "Local Gateway (127.0.0.1)"
            port = self.get_config_value(f"local_gateway_{mode}_port")
        else:
            host = f"Remote TWS ({self.get_config_value('remote_tws_host')})"
            port = self.get_config_value(f"remote_tws_{mode}_port")

        mode_emoji = "📄" if mode == "paper" else "🔴"
        mode_text = "PAPER" if mode == "paper" else "LIVE"

        config_text = f"🎯 Target: {host}:{port} | {mode_emoji} {mode_text} Trading"
        self.config_display.config(text=config_text)

    def get_current_connection_info(self):
        """Get current connection host and port"""
        conn_type = self.connection_type.get()
        mode = self.trading_mode.get()

        if conn_type == "local_gateway":
            host = "127.0.0.1"
            port = int(self.get_config_value(f"local_gateway_{mode}_port"))
        else:
            host = self.get_config_value("remote_tws_host")
            port = int(self.get_config_value(f"remote_tws_{mode}_port"))

        return host, port

    def check_system_status(self):
        """Check system status based on current configuration"""

        def check_in_background():
            host, port = self.get_current_connection_info()

            # Check local gateway process (only for local)
            if self.connection_type.get() == "local_gateway":
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
                    )
                    local_running = bool(result.stdout.strip())
                except:
                    local_running = False
            else:
                local_running = None

            # Test API connection
            api_connected = self.test_api_connection_sync(host, port)

            # Check SPYDER
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "Spyder"], capture_output=True, text=True
                )
                spyder_running = bool(result.stdout.strip())
            except:
                spyder_running = False

            self.root.after(
                0,
                self.update_status_display,
                local_running,
                api_connected,
                spyder_running,
            )

        threading.Thread(target=check_in_background, daemon=True).start()

    def test_api_connection_sync(self, host, port):
        """Synchronous API connection test"""
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False

    def update_status_display(self, local_running, api_connected, spyder_running):
        """Update status display"""
        conn_type = self.connection_type.get()
        host, port = self.get_current_connection_info()

        # Connection status
        if conn_type == "local_gateway":
            if local_running:
                self.connection_status.config(text="✅ IB Gateway: Running locally")
            else:
                self.connection_status.config(text="❌ IB Gateway: Not running")
        else:
            self.connection_status.config(text=f"🌐 Remote TWS: {host}")

        # API status
        if api_connected:
            self.api_status.config(text=f"✅ API: Connected to {host}:{port}")
        else:
            self.api_status.config(text=f"❌ API: Cannot connect to {host}:{port}")

        # SPYDER status
        if spyder_running:
            self.spyder_status.config(text="✅ SPYDER: Running")
        else:
            self.spyder_status.config(text="⚪ SPYDER: Ready to launch")

    def show_progress(self, message):
        """Show progress bar"""
        self.progress_label.config(text=message)
        self.progress_label.pack(pady=(10, 5))
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.progress.start()

        # Disable buttons
        for btn in [
            self.smart_btn,
            self.restart_btn,
            self.test_btn,
            self.dashboard_btn,
        ]:
            btn.config(state="disabled")

        self.root.update()

    def hide_progress(self):
        """Hide progress bar"""
        self.progress.stop()
        self.progress.pack_forget()
        self.progress_label.pack_forget()

        # Re-enable buttons
        for btn in [
            self.smart_btn,
            self.restart_btn,
            self.test_btn,
            self.dashboard_btn,
        ]:
            btn.config(state="normal")

    def smart_launch(self):
        """Smart launch with current configuration"""

        def launch_process():
            host, port = self.get_current_connection_info()
            self.show_progress("🔍 Analyzing system state...")

            # Check if API is already working
            api_working = self.test_api_connection_sync(host, port)

            if api_working:
                self.root.after(
                    0,
                    lambda: self.show_progress(
                        "✅ Connection ready, launching SPYDER..."
                    ),
                )
                time.sleep(1)
                success = self.launch_spyder_dashboard()
            else:
                conn_type = self.connection_type.get()
                if conn_type == "local_gateway":
                    self.root.after(
                        0,
                        lambda: self.show_progress("🚀 Starting Gateway and SPYDER..."),
                    )
                    success = self.launch_local_system()
                else:
                    self.root.after(0, self.hide_progress)
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Connection Error",
                            f"❌ Cannot connect to Remote TWS at {host}:{port}\n\n"
                            "Please ensure:\n"
                            "• TWS is running on remote computer\n"
                            "• API is enabled in TWS\n"
                            "• Network connectivity is working",
                        ),
                    )
                    return

            self.root.after(0, self.hide_progress)

            if success:
                mode = "PAPER" if self.trading_mode.get() == "paper" else "LIVE"
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        f"🎉 SPYDER launched successfully!\n\n"
                        f"• Host: {host}:{port}\n"
                        f"• Mode: {mode} Trading\n\n"
                        f"Your trading system is now operational.",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", "❌ Launch failed. Check logs for details."
                    ),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=launch_process, daemon=True).start()

    def nuclear_restart(self):
        """Nuclear restart (local gateway only)"""
        if self.connection_type.get() != "local_gateway":
            messagebox.showinfo(
                "Not Applicable",
                "Nuclear restart is only for Local IB Gateway.\n\n"
                "For Remote TWS, restart TWS on the remote computer.",
            )
            return

        def restart_process():
            self.show_progress("🔥 Nuclear restart: Stopping processes...")

            # Kill Gateway processes
            try:
                subprocess.run(["pkill", "-9", "-f", "ibgateway"], check=False)
                time.sleep(3)
            except:
                pass

            self.root.after(
                0, lambda: self.show_progress("🚀 Starting fresh Gateway...")
            )
            time.sleep(2)

            success = self.launch_local_system()
            self.root.after(0, self.hide_progress)

            if success:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success", "🎉 Nuclear restart successful!"
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror("Error", "❌ Nuclear restart failed."),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=restart_process, daemon=True).start()

    def test_connection(self):
        """Test current connection"""

        def test_process():
            host, port = self.get_current_connection_info()
            self.show_progress(f"🧪 Testing connection to {host}:{port}...")

            success = self.test_api_connection_sync(host, port)
            self.root.after(0, self.hide_progress)

            mode = "PAPER" if self.trading_mode.get() == "paper" else "LIVE"
            conn_name = (
                "Local Gateway"
                if self.connection_type.get() == "local_gateway"
                else "Remote TWS"
            )

            if success:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Connection Test",
                        f"✅ Connection Test PASSED\n\n"
                        f"• {conn_name}: {host}:{port}\n"
                        f"• Mode: {mode}\n\n"
                        f"System is ready for trading!",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Connection Test",
                        f"❌ Connection Test FAILED\n\n"
                        f"Cannot connect to {conn_name}: {host}:{port}\n"
                        f"Mode: {mode}\n\n"
                        f"Check connection and try again.",
                    ),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=test_process, daemon=True).start()

    def dashboard_only(self):
        """Launch SPYDER Dashboard only"""

        def dashboard_process():
            self.show_progress("📊 Launching SPYDER Dashboard...")
            success = self.launch_spyder_dashboard()
            self.root.after(0, self.hide_progress)

            if success:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Dashboard Launched", "📊 SPYDER Dashboard started!"
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", "❌ Dashboard launch failed."
                    ),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=dashboard_process, daemon=True).start()

    def launch_local_system(self):
        """Launch Dashboard first, then Gateway (better UX)"""
        try:
            # Launch dashboard immediately in disconnected mode
            print("📊 Launching dashboard first...")
            dashboard_launched = self.launch_spyder_dashboard()

            if not dashboard_launched:
                print("❌ Dashboard launch failed")
                return False

            # Give dashboard time to initialize
            time.sleep(2)

            # Now launch Gateway
            gateway_exe = Path.home() / "Jts" / "ibgateway" / "1039" / "ibgateway"

            if gateway_exe.exists():
                # Get credentials from environment
                mode = self.trading_mode.get()

                # Load credentials from bashrc environment
                env = os.environ.copy()

                # Set mode-specific credentials
                if mode == "live":
                    username = env.get("IB_LIVE_USERNAME", env.get("IB_USERNAME", ""))
                    password = env.get("IB_LIVE_PASSWORD", env.get("IB_PASSWORD", ""))
                else:
                    username = env.get("IB_PAPER_USERNAME", env.get("IB_USERNAME", ""))
                    password = env.get("IB_PAPER_PASSWORD", env.get("IB_PASSWORD", ""))

                # Debug: Show credential status
                print(f"🔍 Credential Check:")
                print(f"   Mode: {mode}")
                print(f"   Username: {username if username else 'NOT SET'}")
                print(f"   Password: {'SET' if password else 'NOT SET'}")

                # Try to use IBC for auto-login if available
                ibc_script = Path.home() / "ibc" / "gatewaystart.sh"
                print(f"   IBC script exists: {ibc_script.exists()}")

                if ibc_script.exists() and username and password:
                    # Use IBC for auto-login
                    print(
                        f"✅ Using IBC auto-login for {mode} mode with user: {username}"
                    )

                    # Set IBC environment variables for credentials
                    ibc_env = env.copy()
                    ibc_env["TWSUSERID"] = username
                    ibc_env["TWSPASSWORD"] = password
                    ibc_env["TRADING_MODE"] = mode

                    print(f"🚀 Launching IBC with:")
                    print(f"   Script: {ibc_script}")
                    print(f"   TWSUSERID: {username}")
                    print(f"   TRADING_MODE: {mode}")

                    # Launch IBC with credentials as environment variables
                    # IBC gatewaystart.sh will read TWSUSERID and TWSPASSWORD
                    subprocess.Popen(
                        [str(ibc_script)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=ibc_env,
                    )

                    # Show auto-login message
                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Gateway Starting",
                            f"✅ Dashboard is running!\n\n"
                            f"🔑 Gateway is starting...\n\n"
                            f"Mode: {mode.upper()} Trading\n"
                            f"User: {username}\n\n"
                            f"NOTE: IBC auto-login may not work with Gateway 1039.\n"
                            f"If login fields are empty, enter credentials manually:\n"
                            f"  Username: {username}\n"
                            f"  Password: (from your config)\n\n"
                            f"Dashboard will auto-connect when Gateway is ready.",
                        ),
                    )
                else:
                    # Standard Gateway launch - manual login required
                    print(f"⚠️ Auto-login not available - using manual Gateway launch")
                    if not ibc_script.exists():
                        print(f"   Reason: IBC script not found at {ibc_script}")
                    if not username:
                        print(
                            f"   Reason: Username not set (check .bashrc for IB_PAPER_USERNAME or IB_LIVE_USERNAME)"
                        )
                    if not password:
                        print(
                            f"   Reason: Password not set (check .bashrc for IB_PAPER_PASSWORD or IB_LIVE_PASSWORD)"
                        )

                    subprocess.Popen(
                        [str(gateway_exe)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=env,
                    )

                    # Wait for login
                    mode_display = (
                        "PAPER" if self.trading_mode.get() == "paper" else "LIVE"
                    )

                    self.root.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Gateway Starting",
                            f"✅ Dashboard is running!\n\n"
                            f"🔑 Gateway is starting...\n\n"
                            f"Please login to Gateway:\n"
                            f"1. Enter your credentials\n"
                            f"2. Select {mode_display} Trading mode\n"
                            f"3. Dashboard will auto-connect when ready",
                        ),
                    )

            return True
        except Exception as e:
            print(f"Error launching local system: {e}")
            return False

    def launch_spyder_dashboard(self):
        """Launch SPYDER Dashboard with proper Python path"""
        try:
            # Set environment variables
            host, port = self.get_current_connection_info()
            env = os.environ.copy()
            env["IB_GATEWAY_HOST"] = host
            env["IB_GATEWAY_PORT"] = str(port)
            env["IB_TRADING_MODE"] = self.trading_mode.get()

            # Ensure SPYDER_HOME is in Python path
            spyder_path = str(SPYDER_HOME)
            if spyder_path not in sys.path:
                sys.path.insert(0, spyder_path)

            # Set PYTHONPATH environment variable
            python_path = env.get("PYTHONPATH", "")
            if spyder_path not in python_path:
                env["PYTHONPATH"] = (
                    f"{spyder_path}:{python_path}" if python_path else spyder_path
                )

            # Try different entry points (prioritize production launcher)
            dashboard_scripts = [
                SPYDER_HOME / "launch_dashboard_production.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
            ]

            # Use venv Python if available, otherwise use sys.executable
            python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
            print(f"Using Python: {python_exe}")

            for script in dashboard_scripts:
                if script.exists():
                    print(f"✅ Launching dashboard: {script.name}")
                    os.chdir(SPYDER_HOME)

                    # Launch with proper environment and venv python
                    subprocess.Popen(
                        [python_exe, str(script)],
                        start_new_session=True,
                        env=env,
                        cwd=str(SPYDER_HOME),
                    )
                    return True

            # If no dashboard script found, show helpful error
            messagebox.showerror(
                "Dashboard Not Found",
                f"Could not find SPYDER dashboard scripts.\n\n"
                f"Searched for:\n"
                f"• SpyderG_GUI/SpyderG02_GUIEntry.py\n"
                f"• SpyderA_Core/SpyderA01_Main.py\n"
                f"• launch_dashboard_production.py\n\n"
                f"Please check your SPYDER installation at:\n{SPYDER_HOME}",
            )
            return False
        except Exception as e:
            messagebox.showerror(
                "Dashboard Launch Error",
                f"Error launching dashboard:\n{str(e)}\n\n"
                f"Please check SPYDER installation.",
            )
            return False

    def quick_switch(self):
        """Quick switch between local/remote"""
        current = self.connection_type.get()
        new_type = "remote_tws" if current == "local_gateway" else "local_gateway"

        self.connection_type.set(new_type)
        self.on_config_change()

    def show_settings(self):
        """Show settings dialog"""
        messagebox.showinfo(
            "Settings",
            f"⚙️ SPYDER Configuration\n\n"
            f"Local Gateway:\n"
            f"• Paper Port: {self.get_config_value('local_gateway_paper_port')}\n"
            f"• Live Port: {self.get_config_value('local_gateway_live_port')}\n\n"
            f"Remote TWS:\n"
            f"• Host: {self.get_config_value('remote_tws_host')}\n"
            f"• Paper Port: {self.get_config_value('remote_tws_paper_port')}\n"
            f"• Live Port: {self.get_config_value('remote_tws_live_port')}\n\n"
            f"Config File: {CONFIG_FILE}",
        )

    def show_help(self):
        """Show help dialog"""
        help_text = """🕷️ SPYDER Enhanced Launcher Help

🚀 SMART LAUNCH:
• Auto-detects system state
• Launches optimally based on configuration
• Recommended for daily use

🔥 NUCLEAR RESTART:
• Forces complete Gateway restart (local only)
• Use when Gateway is stuck or unresponsive

🧪 TEST CONNECTION:
• Verifies API connection to configured target
• Good for troubleshooting connection issues

📊 DASHBOARD ONLY:
• Launches SPYDER without connection management
• Fastest option when connection is already working

🏠 LOCAL GATEWAY:
• Uses IB Gateway running on this computer
• Requires Gateway to be installed locally

🌐 REMOTE TWS:
• Connects to TWS running on another computer
• Requires TWS API to be enabled remotely

📄 PAPER TRADING:
• Safe mode using simulated money
• Recommended for testing and development

🔴 LIVE TRADING:
• Uses real money - exercise extreme caution
• Requires proper risk management
"""

        messagebox.showinfo("Help", help_text)

    def run(self):
        """Start the application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    if not SPYDER_HOME.exists():
        messagebox.showerror(
            "Error", f"SPYDER directory not found!\n\nExpected: {SPYDER_HOME}"
        )
        return

    app = SpyderEnhancedLauncher()
    app.run()


if __name__ == "__main__":
    main()
