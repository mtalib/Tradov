#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: patch_launcher_dashboard.py
Purpose: SPYDER Dashboard Path Fix Script

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER Dashboard Path Fix Script

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path

SPYDER_HOME = Path.home() / "Projects" / "Spyder"
LAUNCHER_FILE = SPYDER_HOME / "SpyderG_GUI" / "SpyderG08_IBKRLoginLauncher_Enhanced.py"
BACKUP_FILE = LAUNCHER_FILE.with_suffix('.py.backup')

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{RESET}")

def main():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}SPYDER Dashboard Path Fix Script{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

    # Check if file exists
    if not LAUNCHER_FILE.exists():
        print_error(f"Launcher file not found: {LAUNCHER_FILE}")
        return 1

    print_info(f"Found launcher file: {LAUNCHER_FILE}")

    # Read the file
    try:
        with open(LAUNCHER_FILE, encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print_error(f"Failed to read file: {e}")
        return 1

    # Check if it contains the wrong reference
    if "SpyderG14_Dashboard.py" not in content:
        print_success("File doesn't contain incorrect reference - already fixed!")
        return 0

    print_warning("Found incorrect reference to SpyderG14_Dashboard.py")

    # Create backup
    try:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print_success(f"Created backup: {BACKUP_FILE}")
    except Exception as e:
        print_error(f"Failed to create backup: {e}")
        return 1

    # Fix the content
    # Replace the incorrect dashboard_options list
    old_dashboard_options = '''dashboard_options = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG14_Dashboard.py",
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]'''

    new_dashboard_options = '''dashboard_options = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG05_TradingDashboard.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]'''

    # Try the first pattern
    if old_dashboard_options in content:
        fixed_content = content.replace(old_dashboard_options, new_dashboard_options)
        print_info("Applied fix using pattern 1")
    else:
        # Alternative pattern - just replace any occurrence
        fixed_content = content.replace(
            'SPYDER_HOME / "SpyderG_GUI" / "SpyderG14_Dashboard.py"',
            'SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py"'
        )
        print_info("Applied fix using pattern 2 (simple replacement)")

    # Verify the fix
    if "SpyderG14_Dashboard.py" in fixed_content:
        print_error("Fix failed - incorrect reference still present")
        return 1

    # Write the fixed content
    try:
        with open(LAUNCHER_FILE, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print_success(f"Fixed launcher file: {LAUNCHER_FILE}")
    except Exception as e:
        print_error(f"Failed to write fixed file: {e}")
        # Restore backup
        try:
            with open(BACKUP_FILE, encoding='utf-8') as f:
                backup_content = f.read()
            with open(LAUNCHER_FILE, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            print_warning("Restored backup file")
        except Exception:
            pass
        return 1

    print(f"\n{GREEN}{'='*70}{RESET}")
    print_success("Dashboard path successfully fixed!")
    print(f"{GREEN}{'='*70}{RESET}\n")

    print_info("Changes made:")
    print(f"  {RED}OLD:{RESET} SpyderG14_Dashboard.py")
    print(f"  {GREEN}NEW:{RESET} SpyderG02_GUIEntry.py")
    print()
    print_info(f"Backup saved to: {BACKUP_FILE}")
    print()
    print_success("You can now launch SPYDER Trading System!")
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
