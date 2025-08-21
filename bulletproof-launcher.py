#!/usr/bin/env python3
"""
Bulletproof Spyder Dashboard Launcher
Handles all possible environment issues
"""
import os
import sys
import subprocess
import time
from pathlib import Path

def log_message(msg):
    """Log messages to file"""
    log_file = "/tmp/spyder-bulletproof.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {msg}\\n")
    print(f"[{timestamp}] {msg}")

def setup_environment():
    """Set up complete environment"""
    log_message("Setting up environment...")
    
    # Core environment
    env_vars = {
        'HOME': '/home/adam',
        'USER': 'adam',
        'XDG_SESSION_TYPE': 'wayland',
        'QT_QPA_PLATFORM': 'wayland',
        'GDK_BACKEND': 'wayland',
        'QT_WAYLAND_DECORATION': 'adwaita',
        'PYAUTOGUI_DISABLE_FAIL_SAFE': '1',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        log_message(f"Set {key}={value}")

def main():
    log_message("=== Bulletproof Launcher Started ===")
    
    try:
        # Setup environment
        setup_environment()
        
        # Change to project directory
        project_dir = Path("/home/adam/Projects/Spyder")
        os.chdir(project_dir)
        log_message(f"Changed to directory: {project_dir}")
        
        # Check if files exist
        venv_activate = project_dir / ".venv" / "bin" / "activate"
        advanced_launcher = project_dir / "advanced-wayland-launcher.py"
        
        log_message(f"Virtual env exists: {venv_activate.exists()}")
        log_message(f"Advanced launcher exists: {advanced_launcher.exists()}")
        
        if not advanced_launcher.exists():
            log_message("ERROR: Advanced launcher not found!")
            return 1
        
        # Method 1: Try using subprocess with bash and venv activation
        log_message("Attempting Method 1: Subprocess with venv")
        cmd = [
            "bash", "-c", 
            f"cd {project_dir} && source .venv/bin/activate && python3 advanced-wayland-launcher.py"
        ]
        
        log_message(f"Running command: {' '.join(cmd)}")
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            cwd=str(project_dir),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        log_message(f"Process started with PID: {process.pid}")
        
        # Read output in real time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                log_message(f"Output: {output.strip()}")
        
        exit_code = process.wait()
        log_message(f"Process finished with exit code: {exit_code}")
        
        return exit_code
        
    except Exception as e:
        log_message(f"ERROR: {e}")
        import traceback
        log_message(f"Traceback: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    log_message(f"=== Bulletproof Launcher Finished (exit: {exit_code}) ===")
    sys.exit(exit_code)
