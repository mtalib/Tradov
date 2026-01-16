#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: fix_launcher_dashboard_path.py
Purpose: SPYDER Dashboard Path Diagnostic and Fix Script

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER Dashboard Path Diagnostic and Fix Script

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import subprocess

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*70}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

# Define paths
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
DESKTOP_FILES = [
    Path.home() / ".local" / "share" / "applications" / "spyder-trading.desktop",
    Path.home() / ".local" / "share" / "applications" / "spyder-trading-system.desktop",
    Path("/usr/share/applications/spyder-trading.desktop"),
    Path("/usr/share/applications/spyder-trading-system.desktop"),
]

CONFIG_FILES = [
    SPYDER_HOME / "config" / "launcher_config.ini",
    SPYDER_HOME / "config" / "launcher_config_oauth.ini",
    SPYDER_HOME / "config" / "auth_launcher_config.ini",
]

LAUNCHER_FILES = [
    SPYDER_HOME / "SpyderG_GUI" / "SpyderG08_EnhancedLauncher.py",
    SPYDER_HOME / "SpyderG_GUI" / "SpyderG08_IBKRLoginLauncher_Enhanced.py",
    SPYDER_HOME / "SpyderG_GUI" / "SpyderG08_IBKRLoginLauncher_OAuth.py",
    SPYDER_HOME / "SpyderG_GUI" / "SpyderG08_UserAuthenticationLauncher.py",
]

# Correct dashboard files (in order of preference)
CORRECT_DASHBOARDS = [
    SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
    SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py",
    SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
]

def main():
    print_header("SPYDER Dashboard Path Diagnostic Tool")
    
    # Step 1: Check if wrong file reference exists
    print_info("Step 1: Checking for incorrect dashboard references...")
    wrong_file = SPYDER_HOME / "SpyderG_GUI" / "SpyderG01_Dashboard.py"
    
    if wrong_file.exists():
        print_warning(f"Found: {wrong_file}")
        print_warning("This file should not be the main dashboard entry point!")
    else:
        print_error(f"Missing (as expected): {wrong_file}")
    
    # Step 2: Check correct dashboard files
    print_info("\nStep 2: Checking for correct dashboard files...")
    found_dashboards = []
    for dashboard in CORRECT_DASHBOARDS:
        if dashboard.exists():
            print_success(f"Found: {dashboard}")
            found_dashboards.append(dashboard)
        else:
            print_error(f"Missing: {dashboard}")
    
    if not found_dashboards:
        print_error("❌ NO DASHBOARD FILES FOUND! Project may be incomplete.")
        return
    
    recommended_dashboard = found_dashboards[0]
    print_success(f"\n✅ Recommended dashboard: {recommended_dashboard}")
    
    # Step 3: Check desktop files
    print_info("\nStep 3: Checking desktop launcher files...")
    found_desktop_files = []
    for desktop_file in DESKTOP_FILES:
        if desktop_file.exists():
            print_success(f"Found: {desktop_file}")
            found_desktop_files.append(desktop_file)
            
            # Check content
            try:
                with open(desktop_file, 'r') as f:
                    content = f.read()
                    if "SpyderG01_Dashboard.py" in content:
                        print_error(f"  ⚠️  Contains incorrect reference to SpyderG01_Dashboard.py")
                        print_info(f"  📝 This file needs to be fixed!")
                    else:
                        print_success(f"  ✅ No incorrect references found")
            except Exception as e:
                print_error(f"  ❌ Could not read file: {e}")
    
    if not found_desktop_files:
        print_warning("No desktop files found")
    
    # Step 4: Check config files
    print_info("\nStep 4: Checking configuration files...")
    for config_file in CONFIG_FILES:
        if config_file.exists():
            print_success(f"Found: {config_file}")
            try:
                with open(config_file, 'r') as f:
                    content = f.read()
                    if "SpyderG01_Dashboard.py" in content:
                        print_error(f"  ⚠️  Contains incorrect reference to SpyderG01_Dashboard.py")
                    else:
                        print_success(f"  ✅ No incorrect references found")
            except Exception as e:
                print_error(f"  ❌ Could not read file: {e}")
        else:
            print_warning(f"Not found: {config_file}")
    
    # Step 5: Check launcher Python files
    print_info("\nStep 5: Checking launcher Python scripts...")
    issues_found = []
    for launcher_file in LAUNCHER_FILES:
        if launcher_file.exists():
            print_success(f"Found: {launcher_file}")
            try:
                with open(launcher_file, 'r') as f:
                    content = f.read()
                    if "SpyderG01_Dashboard.py" in content:
                        print_error(f"  ⚠️  Contains incorrect reference to SpyderG01_Dashboard.py")
                        issues_found.append(launcher_file)
                    else:
                        print_success(f"  ✅ No incorrect references found")
            except Exception as e:
                print_error(f"  ❌ Could not read file: {e}")
    
    # Step 6: Generate fix recommendations
    print_header("RECOMMENDATIONS")
    
    if issues_found:
        print_error("Files with incorrect references found:")
        for file in issues_found:
            print(f"  • {file}")
        print("\n")
        print_info("To fix these files, replace 'SpyderG01_Dashboard.py' with:")
        print(f"  {Colors.GREEN}{recommended_dashboard.name}{Colors.RESET}")
    else:
        print_success("No incorrect file references found in launcher scripts!")
    
    # Step 7: Check which launcher is being used
    print_header("IDENTIFYING ACTIVE LAUNCHER")
    
    # Check for most recently modified launcher
    launcher_files_with_mtime = []
    for launcher in LAUNCHER_FILES:
        if launcher.exists():
            mtime = launcher.stat().st_mtime
            launcher_files_with_mtime.append((launcher, mtime))
    
    if launcher_files_with_mtime:
        launcher_files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        print_info("Launcher files by modification time:")
        for launcher, mtime in launcher_files_with_mtime:
            from datetime import datetime
            mod_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  • {launcher.name} - {mod_time}")
        
        print_success(f"\n✅ Most recently modified: {launcher_files_with_mtime[0][0].name}")
    
    # Step 8: Provide fix script
    print_header("AUTOMATED FIX")
    
    print_info("To automatically fix the issue, you can:")
    print(f"1. Create a symbolic link:")
    print(f"   {Colors.GREEN}cd {SPYDER_HOME / 'SpyderG_GUI'}{Colors.RESET}")
    print(f"   {Colors.GREEN}ln -s {recommended_dashboard.name} SpyderG01_Dashboard.py{Colors.RESET}")
    print()
    print(f"2. OR update your launcher to use the correct file:")
    print(f"   {Colors.GREEN}{recommended_dashboard}{Colors.RESET}")
    
    # Ask if user wants to create symlink
    print("\n")
    response = input(f"{Colors.YELLOW}Would you like to create a symbolic link automatically? (y/n): {Colors.RESET}").strip().lower()
    
    if response == 'y':
        try:
            symlink_target = SPYDER_HOME / "SpyderG_GUI" / "SpyderG01_Dashboard.py"
            if symlink_target.exists():
                print_warning(f"Removing existing file: {symlink_target}")
                symlink_target.unlink()
            
            symlink_target.symlink_to(recommended_dashboard.name)
            print_success(f"✅ Created symbolic link: SpyderG01_Dashboard.py -> {recommended_dashboard.name}")
            print_success("✅ You can now try launching SPYDER again!")
        except Exception as e:
            print_error(f"Failed to create symbolic link: {e}")
            print_info("You may need to run this with appropriate permissions")
    
    print("\n" + "="*70)
    print_success("Diagnostic complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
