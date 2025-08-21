#!/usr/bin/env python3
"""
Simple Dock Launcher for Spyder Dashboard
Handles all environment setup internally
"""
import os
import sys
import subprocess
from pathlib import Path

def setup_environment():
    """Set up all required environment variables"""
    os.environ['XDG_SESSION_TYPE'] = 'wayland'
    os.environ['QT_QPA_PLATFORM'] = 'wayland'
    os.environ['GDK_BACKEND'] = 'wayland'
    os.environ['QT_WAYLAND_DECORATION'] = 'adwaita'
    os.environ['HOME'] = '/home/adam'
    os.environ['USER'] = 'adam'

def main():
    # Log to file
    log_file = "/tmp/spyder-simple-launcher.log"
    
    with open(log_file, "a") as f:
        f.write(f"\\n========== {os.popen('date').read().strip()} ==========\\n")
        f.write(f"Simple launcher started\\n")
        f.write(f"Working directory: {os.getcwd()}\\n")
        f.write(f"Python executable: {sys.executable}\\n")
    
    # Set up environment
    setup_environment()
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Activate virtual environment by modifying Python path
    venv_site_packages = project_dir / ".venv/lib/python3.13/site-packages"
    if venv_site_packages.exists():
        sys.path.insert(0, str(venv_site_packages))
        with open(log_file, "a") as f:
            f.write(f"Added venv to Python path: {venv_site_packages}\\n")
    
    # Add project to Python path
    sys.path.insert(0, str(project_dir))
    
    # Set PYTHONPATH
    os.environ['PYTHONPATH'] = str(project_dir)
    
    try:
        with open(log_file, "a") as f:
            f.write(f"Importing advanced launcher...\\n")
        
        # Import and run the advanced launcher
        import advanced_wayland_launcher
        
        with open(log_file, "a") as f:
            f.write(f"Running main function...\\n")
        
        return advanced_wayland_launcher.main()
        
    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"Error: {e}\\n")
            import traceback
            f.write(traceback.format_exc())
        
        # Fallback: try subprocess
        try:
            result = subprocess.run([
                sys.executable, 
                str(project_dir / "advanced-wayland-launcher.py")
            ], cwd=str(project_dir))
            return result.returncode
        except Exception as e2:
            with open(log_file, "a") as f:
                f.write(f"Subprocess error: {e2}\\n")
            return 1

if __name__ == "__main__":
    sys.exit(main())
