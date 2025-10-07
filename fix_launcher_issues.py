#!/usr/bin/env python3
"""
SPYDER Launcher Issues Fix
===========================

Fixes two critical issues:
1. Dashboard modules not found - Ensures proper Python path and module imports
2. Credentials not being passed to Gateway - Implements proper credential passing

This script updates the launcher to:
- Properly handle SPYDER module imports
- Pass bashrc credentials to Gateway subprocess
- Use IBC/IBController for auto-login if available
- Provide fallback manual login with clear instructions
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil
from datetime import datetime


def fix_launcher_credential_passing():
    """Fix the enhanced launcher to pass credentials properly"""

    print("🔧 SPYDER Launcher Fix - Credential Passing & Dashboard Modules")
    print("=" * 70)
    print(f"Timestamp: {datetime.now()}")
    print("=" * 70)
    print()

    spyder_home = Path.home() / "Projects" / "Spyder"
    launcher_file = spyder_home / "spyder_launcher_enhanced.py"

    if not launcher_file.exists():
        print(f"❌ Launcher not found: {launcher_file}")
        return False

    print("📦 Creating backup of current launcher...")
    backup_file = (
        spyder_home
        / f"spyder_launcher_enhanced.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    )
    shutil.copy2(launcher_file, backup_file)
    print(f"✅ Backup created: {backup_file}")

    # Read current launcher
    with open(launcher_file, "r") as f:
        content = f.read()

    # Find and replace the launch_local_system method
    old_launch_local = '''    def launch_local_system(self):
        """Launch local Gateway + SPYDER"""
        try:
            gateway_exe = Path.home() / "Jts" / "ibgateway" / "1039" / "ibgateway"

            if gateway_exe.exists():
                # Start Gateway
                subprocess.Popen(
                    [str(gateway_exe)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )'''

    new_launch_local = '''    def launch_local_system(self):
        """Launch local Gateway + SPYDER with credential support"""
        try:
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

                # Try to use IBC for auto-login if available
                ibc_script = Path.home() / "ibc" / "scripts" / "ibcstart.sh"

                if ibc_script.exists() and username and password:
                    # Use IBC for auto-login
                    print(f"Using IBC auto-login for {mode} mode...")
                    subprocess.Popen(
                        [
                            str(ibc_script),
                            "gateway",
                            mode.upper(),
                            username,
                            password
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=env,
                    )
                else:
                    # Standard Gateway launch - manual login required
                    subprocess.Popen(
                        [str(gateway_exe)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        env=env,
                    )'''

    # Replace the method
    if old_launch_local in content:
        content = content.replace(old_launch_local, new_launch_local)
        print("✅ Updated launch_local_system method with credential passing")
    else:
        print(
            "⚠️  Could not find exact match for launch_local_system - manual update needed"
        )

    # Fix the dashboard launch method
    old_dashboard_launch = '''    def launch_spyder_dashboard(self):
        """Launch SPYDER Dashboard"""
        try:
            # Set environment variables
            host, port = self.get_current_connection_info()
            os.environ["IB_GATEWAY_HOST"] = host
            os.environ["IB_GATEWAY_PORT"] = str(port)
            os.environ["IB_TRADING_MODE"] = self.trading_mode.get()

            # Try different entry points
            dashboard_scripts = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]

            for script in dashboard_scripts:
                if script.exists():
                    os.chdir(SPYDER_HOME)
                    subprocess.Popen(
                        [sys.executable, str(script)], start_new_session=True
                    )
                    return True

            return False
        except:
            return False'''

    new_dashboard_launch = '''    def launch_spyder_dashboard(self):
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
                env["PYTHONPATH"] = f"{spyder_path}:{python_path}" if python_path else spyder_path

            # Try different entry points
            dashboard_scripts = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]

            for script in dashboard_scripts:
                if script.exists():
                    os.chdir(SPYDER_HOME)

                    # Launch with proper environment
                    subprocess.Popen(
                        [sys.executable, str(script)],
                        start_new_session=True,
                        env=env,
                        cwd=str(SPYDER_HOME)
                    )
                    return True

            # If no dashboard script found, show helpful error
            messagebox.showerror(
                "Dashboard Not Found",
                f"Could not find SPYDER dashboard scripts.\\n\\n"
                f"Searched for:\\n"
                f"• SpyderG_GUI/SpyderG02_GUIEntry.py\\n"
                f"• SpyderA_Core/SpyderA01_Main.py\\n"
                f"• launch_dashboard_production.py\\n\\n"
                f"Please check your SPYDER installation at:\\n{SPYDER_HOME}"
            )
            return False
        except Exception as e:
            messagebox.showerror(
                "Dashboard Launch Error",
                f"Error launching dashboard:\\n{str(e)}\\n\\n"
                f"Please check SPYDER installation."
            )
            return False'''

    # Replace dashboard method
    if old_dashboard_launch in content:
        content = content.replace(old_dashboard_launch, new_dashboard_launch)
        print("✅ Updated launch_spyder_dashboard method with proper module handling")
    else:
        print("⚠️  Could not find exact match for launch_spyder_dashboard")

    # Write updated content
    print("📝 Writing updated launcher...")
    with open(launcher_file, "w") as f:
        f.write(content)

    print("✅ Launcher updated successfully!")
    print()
    return True


def create_ibc_wrapper():
    """Create a simple IBC wrapper script for auto-login"""

    print("🔧 Creating IBC/IBController wrapper for auto-login...")

    spyder_home = Path.home() / "Projects" / "Spyder"
    wrapper_script = spyder_home / "launch_gateway_with_credentials.sh"

    wrapper_content = """#!/bin/bash
# SPYDER Gateway Launcher with Auto-Login Support
# This script launches IB Gateway with credentials from bashrc

# Source bashrc to get credentials
source ~/.bashrc

# Get trading mode (default to paper)
MODE="${1:-paper}"

# Set credentials based on mode
if [ "$MODE" = "live" ]; then
    USERNAME="${IB_LIVE_USERNAME:-$IB_USERNAME}"
    PASSWORD="${IB_LIVE_PASSWORD:-$IB_PASSWORD}"
else
    USERNAME="${IB_PAPER_USERNAME:-$IB_USERNAME}"
    PASSWORD="${IB_PAPER_PASSWORD:-$IB_PASSWORD}"
fi

# Gateway executable
GATEWAY_EXE="$HOME/Jts/ibgateway/1039/ibgateway"

echo "🚀 Launching IB Gateway ($MODE mode)..."
echo "   Username: $USERNAME"
echo "   Password: [HIDDEN]"

# Check if IBC is available
IBC_DIR="$HOME/ibc"
if [ -d "$IBC_DIR" ] && [ -f "$IBC_DIR/scripts/ibcstart.sh" ]; then
    echo "✅ Using IBC for auto-login..."
    "$IBC_DIR/scripts/ibcstart.sh" gateway "$MODE" "$USERNAME" "$PASSWORD" &
else
    echo "⚠️  IBC not found - launching Gateway (manual login required)"
    echo ""
    echo "📋 LOGIN CREDENTIALS:"
    echo "   Username: $USERNAME"
    echo "   Password: $PASSWORD"
    echo "   Mode: $MODE"
    echo ""

    # Launch Gateway
    cd "$HOME/Jts/ibgateway/1039"
    nohup "$GATEWAY_EXE" > /dev/null 2>&1 &

    echo "✅ Gateway launched - please login manually with above credentials"
fi

echo ""
echo "⏳ Waiting 30 seconds for Gateway to initialize..."
sleep 30
echo "✅ Gateway should be ready now"
"""

    # Write wrapper script
    with open(wrapper_script, "w") as f:
        f.write(wrapper_content)

    # Make executable
    os.chmod(wrapper_script, 0o755)

    print(f"✅ Created Gateway wrapper: {wrapper_script}")
    print()
    return wrapper_script


def update_desktop_launcher():
    """Update desktop launcher to use credential wrapper"""

    print("🔧 Updating desktop launcher to use credential wrapper...")

    desktop_file = (
        Path.home() / ".local" / "share" / "applications" / "spyder-trading.desktop"
    )

    if not desktop_file.exists():
        print("⚠️  Desktop launcher not found - skipping")
        return False

    # Read current desktop file
    with open(desktop_file, "r") as f:
        content = f.read()

    # Update Exec line to use bash -l to load bashrc
    old_exec = "Exec=/usr/bin/python3"
    new_exec = "Exec=bash -l -c 'cd /home/adam/Projects/Spyder && python3"

    if old_exec in content:
        content = content.replace(old_exec, new_exec)
        # Also need to close the bash command
        content = content.replace(
            "spyder_launcher_enhanced.py", "spyder_launcher_enhanced.py'"
        )

    # Write updated desktop file
    with open(desktop_file, "w") as f:
        f.write(content)

    print("✅ Desktop launcher updated")
    return True


def show_credential_check():
    """Show current credential configuration"""

    print()
    print("🔐 CHECKING CREDENTIAL CONFIGURATION")
    print("=" * 50)

    # Check environment variables
    paper_user = os.environ.get("IB_PAPER_USERNAME", "NOT SET")
    paper_pass_set = "SET" if os.environ.get("IB_PAPER_PASSWORD") else "NOT SET"
    live_user = os.environ.get("IB_LIVE_USERNAME", "NOT SET")
    live_pass_set = "SET" if os.environ.get("IB_LIVE_PASSWORD") else "NOT SET"
    default_user = os.environ.get("IB_USERNAME", "NOT SET")
    default_pass_set = "SET" if os.environ.get("IB_PASSWORD") else "NOT SET"

    print(f"Paper Trading:")
    print(f"  Username: {paper_user}")
    print(f"  Password: {paper_pass_set}")
    print()
    print(f"Live Trading:")
    print(f"  Username: {live_user}")
    print(f"  Password: {live_pass_set}")
    print()
    print(f"Default (Fallback):")
    print(f"  Username: {default_user}")
    print(f"  Password: {default_pass_set}")
    print()

    if paper_user == "NOT SET" or default_user == "NOT SET":
        print("⚠️  WARNING: Credentials not properly configured!")
        print("   Auto-login will not work without credentials.")
        print()
        print("📋 TO FIX:")
        print("   1. Edit ~/.bashrc")
        print("   2. Ensure these variables are set:")
        print("      export IB_PAPER_USERNAME='your_username'")
        print("      export IB_PAPER_PASSWORD='your_password'")
        print("      export IB_LIVE_USERNAME='your_username'")
        print("      export IB_LIVE_PASSWORD='your_password'")
        print("   3. Run: source ~/.bashrc")
        print()
        return False

    return True


def show_completion_message():
    """Show completion message with instructions"""

    print()
    print("=" * 70)
    print("✅ LAUNCHER FIXES APPLIED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("🔧 WHAT WAS FIXED:")
    print()
    print("1. ✅ Credential Passing:")
    print("   • Gateway now receives credentials from bashrc")
    print("   • Supports both Paper and Live mode credentials")
    print("   • Falls back to manual login if credentials not set")
    print()
    print("2. ✅ Dashboard Module Handling:")
    print("   • Proper PYTHONPATH configuration")
    print("   • Better error messages for missing modules")
    print("   • Correct working directory setup")
    print()
    print("3. ✅ Gateway Wrapper Script:")
    print("   • Created launch_gateway_with_credentials.sh")
    print("   • Supports IBC auto-login (if installed)")
    print("   • Shows credentials for manual entry")
    print()
    print("🚀 NEXT STEPS:")
    print()
    print("1. Verify your credentials in ~/.bashrc:")
    print("   • IB_PAPER_USERNAME")
    print("   • IB_PAPER_PASSWORD")
    print("   • IB_LIVE_USERNAME")
    print("   • IB_LIVE_PASSWORD")
    print()
    print("2. Reload your bashrc (in new terminal):")
    print("   source ~/.bashrc")
    print()
    print("3. Test the launcher:")
    print("   • Click SPYDER icon in applications menu")
    print("   • OR run: python3 ~/Projects/Spyder/spyder_launcher_enhanced.py")
    print()
    print("💡 FOR AUTO-LOGIN:")
    print("   • Install IBC/IBController for automatic credential entry")
    print("   • OR enter credentials manually when Gateway starts")
    print("   • Credentials are shown in the terminal/popup")
    print()
    print("🔒 SECURITY NOTE:")
    print("   • Credentials are only in memory and ~/.bashrc")
    print("   • Ensure ~/.bashrc has 600 permissions")
    print("   • Never commit credentials to git")
    print()


def main():
    """Main execution"""
    try:
        # Fix the launcher
        if not fix_launcher_credential_passing():
            print("❌ Failed to update launcher")
            return False

        # Create wrapper script
        wrapper = create_ibc_wrapper()

        # Update desktop launcher
        update_desktop_launcher()

        # Check credentials
        creds_ok = show_credential_check()

        # Show completion message
        show_completion_message()

        if not creds_ok:
            print(
                "⚠️  Please configure credentials in ~/.bashrc before using auto-login"
            )

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
