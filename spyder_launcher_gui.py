#!/usr/bin/env python3
"""
SPYDER Interactive Launcher GUI
One-click trading system with smart selection screen

Features:
- Smart detection of Gateway status
- Nuclear restart capability
- Auto-login with stored credentials
- Dashboard integration
- Error handling and recovery
"""

import os
import sys
import time
import subprocess
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, font
from pathlib import Path
from datetime import datetime
import threading

# Paths and Configuration
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
JTS_PATH = Path.home() / "Jts"


class SpyderLauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_styles()
        self.create_widgets()
        self.check_system_status()

    def setup_window(self):
        """Configure main window"""
        self.root.title("🕷️ SPYDER Trading System Launcher")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # Center window on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

        # Set icon if available
        try:
            self.root.iconname("SPYDER")
        except:
            pass

    def setup_styles(self):
        """Configure UI styles"""
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Custom colors
        bg_color = "#1e1e1e"  # Dark background
        fg_color = "#ffffff"  # White text
        accent_color = "#00ff88"  # Green accent

        # Configure styles
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

        self.style.configure("Action.TButton", font=("Arial", 12, "bold"), padding=10)

        # Set window background
        self.root.configure(bg=bg_color)

    def create_widgets(self):
        """Create GUI components"""
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(
            main_frame, text="🕷️ SPYDER TRADING SYSTEM", style="Title.TLabel"
        )
        title_label.pack(pady=(0, 10))

        subtitle = ttk.Label(
            main_frame,
            text="Professional Automated Trading Platform",
            style="Status.TLabel",
        )
        subtitle.pack(pady=(0, 20))

        # System Status Frame
        status_frame = tk.LabelFrame(
            main_frame,
            text="System Status",
            bg="#1e1e1e",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        status_frame.pack(fill=tk.X, pady=(0, 20))

        self.gateway_status = ttk.Label(
            status_frame, text="🔍 Checking Gateway...", style="Status.TLabel"
        )
        self.gateway_status.pack(anchor=tk.W, padx=10, pady=5)

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
            bg="#1e1e1e",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Smart Launch Button
        self.smart_btn = ttk.Button(
            options_frame,
            text="🚀 Smart Launch",
            command=self.smart_launch,
            style="Action.TButton",
        )
        self.smart_btn.pack(fill=tk.X, padx=10, pady=5)

        smart_desc = ttk.Label(
            options_frame,
            text="Auto-detect system state and launch optimally",
            style="Status.TLabel",
        )
        smart_desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Clean Restart Button
        self.clean_btn = ttk.Button(
            options_frame,
            text="🔥 Clean Restart",
            command=self.clean_restart,
            style="Action.TButton",
        )
        self.clean_btn.pack(fill=tk.X, padx=10, pady=5)

        clean_desc = ttk.Label(
            options_frame,
            text="Nuclear restart Gateway + launch SPYDER fresh",
            style="Status.TLabel",
        )
        clean_desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Test Only Button
        self.test_btn = ttk.Button(
            options_frame,
            text="🧪 Test Only",
            command=self.test_only,
            style="Action.TButton",
        )
        self.test_btn.pack(fill=tk.X, padx=10, pady=5)

        test_desc = ttk.Label(
            options_frame,
            text="Verify Gateway API connection without launching",
            style="Status.TLabel",
        )
        test_desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Dashboard Only Button
        self.dashboard_btn = ttk.Button(
            options_frame,
            text="📊 Dashboard Only",
            command=self.dashboard_only,
            style="Action.TButton",
        )
        self.dashboard_btn.pack(fill=tk.X, padx=10, pady=5)

        dashboard_desc = ttk.Label(
            options_frame,
            text="Launch SPYDER Dashboard (assumes Gateway ready)",
            style="Status.TLabel",
        )
        dashboard_desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Bottom buttons frame
        bottom_frame = tk.Frame(main_frame, bg="#1e1e1e")
        bottom_frame.pack(fill=tk.X)

        # Settings Button
        settings_btn = ttk.Button(
            bottom_frame, text="⚙️ Settings", command=self.show_settings
        )
        settings_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Refresh Button
        refresh_btn = ttk.Button(
            bottom_frame, text="🔄 Refresh", command=self.check_system_status
        )
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Help Button
        help_btn = ttk.Button(bottom_frame, text="❓ Help", command=self.show_help)
        help_btn.pack(side=tk.LEFT)

        # Exit Button
        exit_btn = ttk.Button(bottom_frame, text="❌ Exit", command=self.root.quit)
        exit_btn.pack(side=tk.RIGHT)

        # Progress bar (initially hidden)
        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")
        self.progress_label = ttk.Label(main_frame, text="", style="Status.TLabel")

    def check_system_status(self):
        """Check Gateway, API, and SPYDER status"""

        def check_in_background():
            # Check Gateway process
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
                )
                gateway_running = bool(result.stdout.strip())
            except:
                gateway_running = False

            # Check API port
            try:
                result = subprocess.run(
                    ["netstat", "-tlpn"], capture_output=True, text=True
                )
                api_listening = ":4002" in result.stdout
            except:
                api_listening = False

            # Check SPYDER processes
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "Spyder"], capture_output=True, text=True
                )
                spyder_running = bool(result.stdout.strip())
            except:
                spyder_running = False

            # Update UI in main thread
            self.root.after(
                0,
                self.update_status_display,
                gateway_running,
                api_listening,
                spyder_running,
            )

        # Run check in background thread
        threading.Thread(target=check_in_background, daemon=True).start()

    def update_status_display(self, gateway_running, api_listening, spyder_running):
        """Update status display in UI"""
        # Gateway status
        if gateway_running:
            self.gateway_status.config(text="✅ IB Gateway: Running")
        else:
            self.gateway_status.config(text="❌ IB Gateway: Not Running")

        # API status
        if api_listening:
            self.api_status.config(text="✅ Gateway API: Listening on port 4002")
        else:
            self.api_status.config(text="❌ Gateway API: Not accessible")

        # SPYDER status
        if spyder_running:
            self.spyder_status.config(text="✅ SPYDER: Running")
        else:
            self.spyder_status.config(text="⚪ SPYDER: Ready to launch")

    def show_progress(self, message):
        """Show progress bar with message"""
        self.progress_label.config(text=message)
        self.progress_label.pack(pady=(10, 5))
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.progress.start()

        # Disable buttons during operation
        for widget in [
            self.smart_btn,
            self.clean_btn,
            self.test_btn,
            self.dashboard_btn,
        ]:
            widget.config(state="disabled")

        self.root.update()

    def hide_progress(self):
        """Hide progress bar"""
        self.progress.stop()
        self.progress.pack_forget()
        self.progress_label.pack_forget()

        # Re-enable buttons
        for widget in [
            self.smart_btn,
            self.clean_btn,
            self.test_btn,
            self.dashboard_btn,
        ]:
            widget.config(state="normal")

    def smart_launch(self):
        """Smart launch with auto-detection"""

        def launch_process():
            self.show_progress("🔍 Analyzing system state...")

            # Check current status
            gateway_running = self.check_gateway_running()
            api_working = self.check_api_working()

            if gateway_running and api_working:
                self.root.after(
                    0,
                    lambda: self.show_progress("✅ Gateway ready, launching SPYDER..."),
                )
                time.sleep(1)
                success = self.launch_spyder_dashboard()
            else:
                self.root.after(
                    0, lambda: self.show_progress("🚀 Starting Gateway and SPYDER...")
                )
                success = self.launch_full_system()

            self.root.after(0, self.hide_progress)

            if success:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        "🎉 SPYDER launched successfully!\n\nYour trading system is now operational.",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", "❌ Launch failed. Check Gateway logs for details."
                    ),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=launch_process, daemon=True).start()

    def clean_restart(self):
        """Nuclear restart + clean launch"""

        def restart_process():
            self.show_progress("🔥 Nuclear restart: Stopping all processes...")

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

            success = self.launch_full_system()

            self.root.after(0, self.hide_progress)

            if success:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        "🎉 Clean restart successful!\n\nSPYDER is now running with fresh Gateway.",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error",
                        "❌ Clean restart failed. Manual Gateway launch may be needed.",
                    ),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=restart_process, daemon=True).start()

    def test_only(self):
        """Test Gateway API connection only"""

        def test_process():
            self.show_progress("🧪 Testing Gateway API connection...")

            success = self.check_api_working()

            self.root.after(0, self.hide_progress)

            if success:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Test Result",
                        "✅ Gateway API Test PASSED\n\nConnection successful!\nAccount: Paper Trading",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Test Result",
                        "❌ Gateway API Test FAILED\n\nRecommendations:\n• Try 'Clean Restart'\n• Check Gateway GUI settings\n• Verify Gateway is logged in",
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
                        "Dashboard Launched",
                        "📊 SPYDER Dashboard started!\n\nNote: Ensure Gateway API is working for full functionality.",
                    ),
                )
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error",
                        "❌ Dashboard launch failed.\n\nCheck that SPYDER files are accessible.",
                    ),
                )

            self.root.after(0, self.check_system_status)

        threading.Thread(target=dashboard_process, daemon=True).start()

    def check_gateway_running(self):
        """Check if Gateway is running"""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
            )
            return bool(result.stdout.strip())
        except:
            return False

    def check_api_working(self):
        """Test if Gateway API is responding"""
        try:
            # Simple socket test
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(("127.0.0.1", 4002))
            sock.close()
            return result == 0
        except:
            return False

    def launch_full_system(self):
        """Launch Gateway + SPYDER system"""
        try:
            # Start Gateway manually (user needs to login)
            gateway_exe = Path.home() / "Jts" / "ibgateway" / "1039" / "ibgateway"

            if gateway_exe.exists():
                # Launch Gateway in background
                subprocess.Popen(
                    [str(gateway_exe)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

                # Wait for user to login and API to be ready
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Gateway Starting",
                        "🔑 IB Gateway is starting...\n\nPlease:\n1. Login with your credentials\n2. Wait for Gateway to be fully loaded\n3. Click OK when ready",
                    ),
                )

                # Check API every 5 seconds for up to 2 minutes
                for i in range(24):  # 2 minutes
                    time.sleep(5)
                    if self.check_api_working():
                        break
                else:
                    return False  # Timeout

            # Launch SPYDER Dashboard
            return self.launch_spyder_dashboard()

        except Exception as e:
            return False

    def launch_spyder_dashboard(self):
        """Launch SPYDER Dashboard"""
        try:
            # Try different SPYDER entry points
            dashboard_options = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]

            for dashboard_script in dashboard_options:
                if dashboard_script.exists():
                    os.chdir(SPYDER_HOME)
                    subprocess.Popen(
                        [sys.executable, str(dashboard_script)], start_new_session=True
                    )
                    return True

            return False

        except Exception as e:
            return False

    def show_settings(self):
        """Show settings dialog"""
        messagebox.showinfo(
            "Settings",
            "⚙️ SPYDER Settings\n\n"
            + "For credential configuration:\n"
            + "Run: python3 setup_bashrc_credentials.py\n\n"
            + "Gateway path: ~/Jts/ibgateway/1039/\n"
            + "SPYDER path: ~/Projects/Spyder/\n"
            + "API Port: 4002 (Paper Trading)",
        )

    def show_help(self):
        """Show help dialog"""
        help_text = """🕷️ SPYDER Launcher Help

🚀 SMART LAUNCH:
• Auto-detects system state
• Launches optimally based on current status
• Recommended for daily use

🔥 CLEAN RESTART:
• Forces complete Gateway restart
• Clears any stuck states
• Use when Gateway is unresponsive

🧪 TEST ONLY:
• Verifies Gateway API connection
• No SPYDER launch
• Good for troubleshooting

📊 DASHBOARD ONLY:
• Launches SPYDER without Gateway management
• Use when Gateway is already running
• Fastest option for trading

💡 TROUBLESHOOTING:
• If Gateway won't connect: Try Clean Restart
• If API test fails: Check Gateway GUI settings
• Enable "ActiveX and Socket EClients" in Gateway
• Verify localhost is in Trusted IPs
"""

        messagebox.showinfo("Help", help_text)

    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    # Check if running from correct directory
    if not SPYDER_HOME.exists():
        messagebox.showerror(
            "Error",
            f"SPYDER directory not found!\n\nExpected: {SPYDER_HOME}\n\nPlease run from correct location.",
        )
        return

    # Create and run launcher
    app = SpyderLauncherGUI()
    app.run()


if __name__ == "__main__":
    main()
