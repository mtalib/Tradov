#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Simple Launcher
A straightforward launcher for the Spyder Trading System
"""

import os
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

# ==============================================================================
# CONFIGURATION
# ==============================================================================
def find_spyder_home():
    """Find the Spyder installation directory"""
    possible_paths = [
        Path.home() / "Projects" / "Spyder",
        Path.home() / "Spyder",
        Path("/home/adam/Projects/Spyder"),
        Path.cwd()
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "SpyderA_Core" / "SpyderA01_Main.py").exists():
            return path
    
    return None

def check_requirements():
    """Check if required modules are available"""
    issues = []
    
    try:
        import PyQt6
    except ImportError:
        issues.append("PyQt6 not installed")
    
    try:
        import pandas
    except ImportError:
        issues.append("pandas not installed")
    
    try:
        import ib_insync
    except ImportError:
        try:
            import ib_async
        except ImportError:
            issues.append("Neither ib_insync nor ib_async installed")
    
    return issues

def check_ib_gateway():
    """Check if IB Gateway is running"""
    try:
        # Check if Java process with ibgateway is running
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except:
        # If pgrep doesn't exist, try ps
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True
            )
            return "ibgateway" in result.stdout.lower()
        except:
            return False

def launch_spyder_gui(spyder_home):
    """Launch Spyder with GUI"""
    sys.path.insert(0, str(spyder_home))
    
    try:
        # Try to import and run the main module
        from SpyderG_GUI import SpyderG01_MainWindow
        from SpyderA_Core import SpyderA01_Main
        from PyQt6.QtWidgets import QApplication
        
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Trading System")
        
        # Create and show main window
        window = SpyderG01_MainWindow.MainWindow()
        window.show()
        
        # Start the application
        sys.exit(app.exec())
        
    except ImportError as e:
        error_msg = f"Failed to import Spyder modules:\n{str(e)}"
        print(error_msg)
        messagebox.showerror("Import Error", error_msg)
        
        # Try alternative launch method
        try_alternative_launch(spyder_home)

def try_alternative_launch(spyder_home):
    """Try alternative launch methods"""
    print("\nTrying alternative launch methods...")
    
    # Method 1: Direct Python script execution
    main_script = spyder_home / "SpyderA_Core" / "SpyderA01_Main.py"
    if main_script.exists():
        print(f"Launching {main_script}...")
        subprocess.run([sys.executable, str(main_script), "--gui"])
        return
    
    # Method 2: Q-Script launcher
    q_launcher = spyder_home / "SpyderQ_Scripts" / "SpyderQ14_MainLauncher.py"
    if q_launcher.exists():
        print(f"Launching {q_launcher}...")
        subprocess.run([sys.executable, str(q_launcher), "--gui"])
        return
    
    # Method 3: Shell script
    shell_launcher = spyder_home / "SpyderQ_Scripts" / "SpyderQ10_StartAll.sh"
    if shell_launcher.exists():
        print(f"Launching {shell_launcher}...")
        subprocess.run(["bash", str(shell_launcher)])
        return
    
    print("No alternative launch method found!")
    messagebox.showerror("Launch Error", "Could not find any way to launch Spyder")

def show_startup_dialog():
    """Show a startup dialog with system checks"""
    root = tk.Tk()
    root.title("Spyder Trading System Launcher")
    root.geometry("500x400")
    
    # Header
    header = tk.Label(root, text="SPYDER TRADING SYSTEM", font=("Arial", 16, "bold"))
    header.pack(pady=10)
    
    # Status text
    status_text = tk.Text(root, height=15, width=60)
    status_text.pack(pady=10)
    
    # Check Spyder installation
    status_text.insert("end", "Checking Spyder installation...\n")
    root.update()
    
    spyder_home = find_spyder_home()
    if spyder_home:
        status_text.insert("end", f"✓ Found Spyder at: {spyder_home}\n", "success")
        status_text.tag_config("success", foreground="green")
    else:
        status_text.insert("end", "✗ Could not find Spyder installation\n", "error")
        status_text.tag_config("error", foreground="red")
        messagebox.showerror("Error", "Could not find Spyder installation!")
        return None
    
    # Check requirements
    status_text.insert("end", "\nChecking Python requirements...\n")
    root.update()
    
    issues = check_requirements()
    if issues:
        for issue in issues:
            status_text.insert("end", f"✗ {issue}\n", "error")
    else:
        status_text.insert("end", "✓ All requirements installed\n", "success")
    
    # Check IB Gateway
    status_text.insert("end", "\nChecking IB Gateway...\n")
    root.update()
    
    if check_ib_gateway():
        status_text.insert("end", "✓ IB Gateway is running\n", "success")
    else:
        status_text.insert("end", "⚠ IB Gateway may not be running\n", "warning")
        status_text.tag_config("warning", foreground="orange")
    
    status_text.insert("end", "\n" + "="*50 + "\n")
    status_text.insert("end", "Ready to launch Spyder Trading System\n")
    
    # Launch button
    def launch():
        root.destroy()
        launch_spyder_gui(spyder_home)
    
    launch_btn = tk.Button(root, text="LAUNCH SPYDER", command=launch, 
                          bg="green", fg="white", font=("Arial", 12, "bold"),
                          padx=20, pady=10)
    launch_btn.pack(pady=20)
    
    # Cancel button
    cancel_btn = tk.Button(root, text="Cancel", command=root.destroy)
    cancel_btn.pack()
    
    root.mainloop()
    return spyder_home

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point"""
    print("="*60)
    print("SPYDER TRADING SYSTEM - SIMPLE LAUNCHER")
    print("="*60)
    
    # Command line mode (no dialog)
    if "--no-dialog" in sys.argv or "--headless" in sys.argv:
        spyder_home = find_spyder_home()
        if not spyder_home:
            print("ERROR: Could not find Spyder installation!")
            sys.exit(1)
        
        print(f"Spyder Home: {spyder_home}")
        
        # Add to path and launch
        sys.path.insert(0, str(spyder_home))
        launch_spyder_gui(spyder_home)
    
    # GUI mode (with dialog)
    else:
        show_startup_dialog()

if __name__ == "__main__":
    main()
