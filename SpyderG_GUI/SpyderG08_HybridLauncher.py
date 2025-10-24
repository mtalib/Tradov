#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_HybridLauncher.py
Purpose: Hybrid launcher that works with BOTH IB Gateway and Client Portal

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-23 Time: 19:00:00
Version: 2.1.0

Module Description:
    Smart launcher that automatically detects which gateway is available:
    - Client Portal Gateway (port 5000) - Modern Web API
    - Traditional IB Gateway (port 4001/4002) - Classic API
    
    Uses whichever is available, or prompts user to start one.
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
from pathlib import Path
from typing import Optional, Tuple

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False
    print("ERROR: tkinter is required")
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
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
IB_GATEWAY_DIR = Path.home() / "Jts" / "ibgateway" / "1039"

# Port configuration
CLIENT_PORTAL_PORT = 5000
IB_GATEWAY_PAPER_PORT = 4002
IB_GATEWAY_LIVE_PORT = 4001

# ==============================================================================
# GATEWAY DETECTION
# ==============================================================================
def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a port is open and accepting connections"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def detect_available_gateway() -> Tuple[str, int]:
    """
    Detect which gateway is running.
    
    Returns:
        Tuple of (gateway_type, port) where gateway_type is:
        - "client_portal" for Client Portal Gateway (port 5000)
        - "ib_gateway_paper" for IB Gateway paper (port 4002)
        - "ib_gateway_live" for IB Gateway live (port 4001)
        - "none" if no gateway detected
    """
    if check_port("localhost", CLIENT_PORTAL_PORT):
        return ("client_portal", CLIENT_PORTAL_PORT)
    elif check_port("localhost", IB_GATEWAY_PAPER_PORT):
        return ("ib_gateway_paper", IB_GATEWAY_PAPER_PORT)
    elif check_port("localhost", IB_GATEWAY_LIVE_PORT):
        return ("ib_gateway_live", IB_GATEWAY_LIVE_PORT)
    else:
        return ("none", 0)

# ==============================================================================
# HYBRID LAUNCHER
# ==============================================================================
class HybridSpyderLauncher:
    """Launcher that works with both IB Gateway types"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__) if HAS_LOGGER else logging.getLogger()
        self.logger.info("Initializing Hybrid SPYDER Launcher")
        
        # Detect gateway
        self.gateway_type, self.gateway_port = detect_available_gateway()
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title("SPYDER Trading System - Launch Options")
        self.root.geometry("600x650")
        self.root.resizable(False, False)
        
        # Center window
        self._center_window()
        
        # Colors
        self.colors = {
            'bg': '#1e1e1e',
            'fg': '#ffffff',
            'accent': '#00ff00',
            'warning': '#ff6b00',
            'error': '#ff0000',
            'button': '#2d2d2d',
        }
        self.root.configure(bg=self.colors['bg'])
        
        # Create UI
        self._create_widgets()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _center_window(self):
        """Center window on screen"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create UI widgets"""
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=30, pady=30)
        
        # Header
        tk.Label(
            main_frame,
            text="🕷️ SPYDER AUTONOMOUS OPTIONS TRADING SYSTEM",
            font=("Arial", 14, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['accent'],
        ).pack(pady=(0, 20))
        
        # Gateway Status Box
        status_frame = tk.Frame(main_frame, bg=self.colors['button'], relief='ridge', bd=2)
        status_frame.pack(fill='x', pady=(0, 20))
        
        if self.gateway_type == "none":
            status_color = self.colors['error']
            status_icon = "❌"
            status_text = "NO GATEWAY DETECTED"
            status_detail = (
                "Please start one of:\n"
                "• Client Portal Gateway (port 5000)\n"
                "• IB Gateway (port 4001 or 4002)"
            )
        elif self.gateway_type == "client_portal":
            status_color = self.colors['accent']
            status_icon = "✅"
            status_text = "CLIENT PORTAL GATEWAY DETECTED"
            status_detail = f"Port {self.gateway_port} - Modern Web API"
        else:
            status_color = self.colors['accent']
            status_icon = "✅"
            status_text = "IB GATEWAY DETECTED"
            mode = "Paper Trading" if self.gateway_port == 4002 else "Live Trading"
            status_detail = f"Port {self.gateway_port} - {mode}"
        
        tk.Label(
            status_frame,
            text=f"{status_icon} {status_text}",
            font=("Arial", 12, "bold"),
            bg=self.colors['button'],
            fg=status_color,
        ).pack(pady=(10, 5))
        
        tk.Label(
            status_frame,
            text=status_detail,
            font=("Arial", 9),
            bg=self.colors['button'],
            fg=self.colors['fg'],
            justify='center'
        ).pack(pady=(0, 10))
        
        # Launch Options
        tk.Label(
            main_frame,
            text="SELECT LAUNCH MODE:",
            font=("Arial", 11, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['fg'],
        ).pack(anchor='w', pady=(10, 10))
        
        # Dashboard Only
        dashboard_btn = tk.Button(
            main_frame,
            text="📊 DASHBOARD ONLY\nVisualization Mode (No Gateway Required)",
            font=("Arial", 11),
            bg=self.colors['button'],
            fg=self.colors['fg'],
            activebackground=self.colors['accent'],
            activeforeground=self.colors['bg'],
            command=self.launch_dashboard_only,
            cursor="hand2",
            relief='raised',
            bd=2,
            padx=20,
            pady=15,
            justify='center'
        )
        dashboard_btn.pack(fill='x', pady=5)
        
        # Paper Trading (if gateway available)
        if self.gateway_type != "none":
            paper_btn = tk.Button(
                main_frame,
                text="📄 PAPER TRADING\nConnect to IBKR and Launch",
                font=("Arial", 11),
                bg=self.colors['button'],
                fg=self.colors['fg'],
                activebackground=self.colors['accent'],
                activeforeground=self.colors['bg'],
                command=self.launch_paper_trading,
                cursor="hand2",
                relief='raised',
                bd=2,
                padx=20,
                pady=15,
                justify='center'
            )
            paper_btn.pack(fill='x', pady=5)
            
            # Live Trading (if gateway available)
            live_btn = tk.Button(
                main_frame,
                text="🔴 LIVE TRADING\n⚠️ REAL MONEY - Be Careful!",
                font=("Arial", 11),
                bg=self.colors['button'],
                fg=self.colors['warning'],
                activebackground=self.colors['error'],
                activeforeground=self.colors['fg'],
                command=self.launch_live_trading,
                cursor="hand2",
                relief='raised',
                bd=2,
                padx=20,
                pady=15,
                justify='center'
            )
            live_btn.pack(fill='x', pady=5)
        
        # Help button
        help_btn = tk.Button(
            main_frame,
            text="❓ HELP",
            font=("Arial", 10),
            bg=self.colors['button'],
            fg=self.colors['fg'],
            command=self.show_help,
            cursor="hand2",
            relief='raised',
            bd=1,
            padx=15,
            pady=8
        )
        help_btn.pack(pady=(20, 0))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready to launch")
        status_bar = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Arial", 9),
            bg=self.colors['button'],
            fg=self.colors['fg'],
            anchor='w',
            relief='sunken',
            bd=1
        )
        status_bar.pack(fill='x', side='bottom', pady=(20, 0))
    
    def launch_dashboard_only(self):
        """Launch dashboard in visualization mode"""
        self.status_var.set("Launching dashboard in visualization mode...")
        self.logger.info("Launching dashboard only")
        
        # Launch dashboard
        dashboard_script = SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py"
        
        if not dashboard_script.exists():
            messagebox.showerror("Error", f"Dashboard not found at:\n{dashboard_script}")
            self.status_var.set("Error: Dashboard not found")
            return
        
        try:
            env = os.environ.copy()
            env["SPYDER_MODE"] = "visualization"
            env["SPYDER_DESKTOP_FILE_NAME"] = "spyder-trading-system"
            
            subprocess.Popen(
                [sys.executable, str(dashboard_script)],
                env=env,
                start_new_session=True
            )
            
            self.logger.info("Dashboard launched successfully")
            messagebox.showinfo("Success", "Dashboard launched in visualization mode!")
            time.sleep(0.5)
            self.root.destroy()
        except Exception as e:
            self.logger.error(f"Failed to launch dashboard: {e}")
            messagebox.showerror("Error", f"Failed to launch dashboard:\n{e}")
            self.status_var.set("Error launching dashboard")
    
    def launch_paper_trading(self):
        """Launch with paper trading connection"""
        if self.gateway_type == "client_portal":
            self._launch_with_client_portal("paper")
        else:
            self._launch_with_ib_gateway("paper")
    
    def launch_live_trading(self):
        """Launch with live trading connection"""
        # Confirm user wants live trading
        response = messagebox.askyesno(
            "⚠️ Live Trading Warning",
            "You are about to connect to LIVE TRADING.\n\n"
            "This uses REAL MONEY and you can LOSE MONEY.\n\n"
            "Are you sure you want to continue?",
            icon='warning'
        )
        
        if not response:
            return
        
        if self.gateway_type == "client_portal":
            self._launch_with_client_portal("live")
        else:
            self._launch_with_ib_gateway("live")
    
    def _launch_with_client_portal(self, mode: str):
        """Launch using Client Portal Web API"""
        import webbrowser
        
        self.status_var.set(f"Connecting to Client Portal ({mode})...")
        self.logger.info(f"Launching with Client Portal - {mode} mode")
        
        # Open browser for authentication
        login_url = "https://localhost:5000/sso/Login?forwardTo=22&RL=1&ip2loc=on"
        
        messagebox.showinfo(
            "Browser Authentication",
            f"Browser will open for IBKR {mode.upper()} authentication.\n\n"
            "Please complete the login process.\n\n"
            "Dashboard will launch automatically after authentication."
        )
        
        webbrowser.open(login_url)
        
        # For now, just launch dashboard after delay
        # TODO: Implement proper auth polling
        self.status_var.set("Please complete login in browser...")
        
        def wait_and_launch():
            time.sleep(10)  # Give user time to log in
            self.root.after(0, lambda: self._launch_dashboard(mode))
        
        threading.Thread(target=wait_and_launch, daemon=True).start()
    
    def _launch_with_ib_gateway(self, mode: str):
        """Launch using traditional IB Gateway"""
        self.status_var.set(f"Connecting to IB Gateway ({mode})...")
        self.logger.info(f"Launching with IB Gateway - {mode} mode")
        
        messagebox.showinfo(
            "IB Gateway Connection",
            f"Connecting to IB Gateway ({mode} mode).\n\n"
            "Dashboard will launch in a moment."
        )
        
        # Launch dashboard
        self._launch_dashboard(mode)
    
    def _launch_dashboard(self, mode: str):
        """Launch the SPYDER dashboard"""
        dashboard_options = [
            SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py",
            SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
            SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
        ]
        
        for dashboard_script in dashboard_options:
            if dashboard_script.exists():
                try:
                    env = os.environ.copy()
                    env["SPYDER_MODE"] = mode
                    env["SPYDER_GATEWAY_TYPE"] = self.gateway_type
                    env["SPYDER_GATEWAY_PORT"] = str(self.gateway_port)
                    env["SPYDER_DESKTOP_FILE_NAME"] = "spyder-trading-system"
                    
                    subprocess.Popen(
                        [sys.executable, str(dashboard_script)],
                        env=env,
                        start_new_session=True
                    )
                    
                    self.logger.info("Dashboard launched successfully")
                    self.status_var.set("Dashboard launched successfully!")
                    time.sleep(0.5)
                    self.root.destroy()
                    return
                except Exception as e:
                    self.logger.error(f"Failed to launch dashboard: {e}")
        
        messagebox.showerror("Error", "Dashboard executable not found")
        self.status_var.set("Error: Dashboard not found")
    
    def show_help(self):
        """Show help dialog"""
        help_text = f"""🕷️ SPYDER Hybrid Launcher Help

GATEWAY STATUS:
{self._get_gateway_status_text()}

LAUNCH MODES:

📊 Dashboard Only
• Visualization and analysis only
• No IBKR connection required
• Uses simulated data

📄 Paper Trading
• Safe testing with virtual money
• Requires gateway running
• All features available

🔴 Live Trading
• REAL MONEY trading
• Risk of financial loss
• Requires gateway running

GATEWAY TYPES:

Client Portal Gateway (Port 5000)
• Modern Web API
• Browser authentication
• Download from IBKR website

IB Gateway (Port 4001/4002)
• Traditional API
• Already installed at: ~/Jts/ibgateway/
• Port 4002 = Paper, Port 4001 = Live

HOW TO START A GATEWAY:

Client Portal:
1. Download from IBKR website
2. Extract and run: ./bin/run.sh root/conf.yaml

IB Gateway:
1. Already installed
2. Run: ~/Jts/ibgateway/ibgateway
3. Configure for paper or live

Version: 2.1.0 (Hybrid)
"""
        messagebox.showinfo("Help", help_text)
    
    def _get_gateway_status_text(self) -> str:
        """Get gateway status description"""
        if self.gateway_type == "none":
            return "❌ No gateway detected\n   Start Client Portal or IB Gateway first"
        elif self.gateway_type == "client_portal":
            return f"✅ Client Portal Gateway (Port {self.gateway_port})\n   Modern Web API ready"
        elif self.gateway_type == "ib_gateway_paper":
            return f"✅ IB Gateway Paper (Port {self.gateway_port})\n   Traditional API ready"
        else:
            return f"✅ IB Gateway Live (Port {self.gateway_port})\n   Traditional API ready"
    
    def on_closing(self):
        """Handle window close"""
        self.root.destroy()
    
    def run(self):
        """Run the launcher"""
        self.root.mainloop()

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    launcher = HybridSpyderLauncher()
    launcher.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
