#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: install_spyder_desktop_launcher.py
Purpose: SPYDER Desktop Launcher Installation Script

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER Desktop Launcher Installation Script

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
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import subprocess

class SpyderDesktopInstaller:
    def __init__(self):
        self.home = Path.home()
        self.spyder_home = self.home / "Projects" / "Spyder"
        self.icon_path = self.home / ".local" / "share" / "icons" / "Spyder-Icon.png"
        self.desktop_dir = self.home / ".local" / "share" / "applications"
        self.desktop_file = self.desktop_dir / "spyder-trading.desktop"

    def print_header(self):
        """Print installation header"""
        print("=" * 70)
        print("🕷️  SPYDER TRADING SYSTEM - Desktop Launcher Installation")
        print("=" * 70)
        print(f"Timestamp: {datetime.now()}")
        print("=" * 70)
        print()

    def check_prerequisites(self):
        """Check if all required files exist"""
        print("🔍 Checking prerequisites...")

        checks = []

        # Check SPYDER home
        if self.spyder_home.exists():
            print(f"✅ SPYDER Home found: {self.spyder_home}")
            checks.append(True)
        else:
            print(f"❌ SPYDER Home not found: {self.spyder_home}")
            checks.append(False)

        # Check launcher script
        launcher_script = self.spyder_home / "spyder_launcher_enhanced.py"
        if launcher_script.exists():
            print(f"✅ Launcher script found: {launcher_script}")
            checks.append(True)
        else:
            print(f"❌ Launcher script not found: {launcher_script}")
            checks.append(False)

        # Check icon
        if self.icon_path.exists():
            print(f"✅ Icon found: {self.icon_path}")
            checks.append(True)
        else:
            print(f"❌ Icon not found: {self.icon_path}")
            print(f"   Looking for alternate icon locations...")

            # Try alternate locations
            alt_icons = [
                self.home
                / ".local"
                / "share"
                / "icons"
                / "hicolor"
                / "512x512"
                / "apps"
                / "spyder-trading.png",
                self.spyder_home / "assets" / "Spyder-Icon.png",
                self.spyder_home / "assets" / "spider-icon.png",
            ]

            for alt_icon in alt_icons:
                if alt_icon.exists():
                    self.icon_path = alt_icon
                    print(f"✅ Using alternate icon: {self.icon_path}")
                    checks.append(True)
                    break
            else:
                print(f"⚠️  No icon found - will use system default")
                self.icon_path = None
                checks.append(True)  # Non-critical

        print()
        return all(checks)

    def create_desktop_file(self):
        """Create the .desktop file"""
        print("📝 Creating desktop launcher file...")

        # Ensure directory exists
        self.desktop_dir.mkdir(parents=True, exist_ok=True)

        # Prepare icon path
        icon_line = (
            f"Icon={self.icon_path}"
            if self.icon_path
            else "Icon=applications-development"
        )

        # Create desktop file content
        desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=SPYDER Trading System
GenericName=Automated Trading Platform
Comment=Professional algorithmic trading system with IB Gateway integration
Exec={sys.executable} {self.spyder_home}/spyder_launcher_enhanced.py
{icon_line}
Terminal=false
Categories=Office;Finance;Development;
Keywords=trading;stocks;options;market;finance;algorithmic;automated;
StartupNotify=true
StartupWMClass=SPYDER

# Actions for right-click menu
Actions=PaperTrading;LiveTrading;RemoteTWS;TestConnection;NuclearRestart;

[Desktop Action PaperTrading]
Name=Paper Trading (Safe)
Exec=bash -c "cd {self.spyder_home} && source ~/.bashrc && python3 spyder_launcher_enhanced.py --mode=paper"
Icon={icon_line.split("=")[1]}

[Desktop Action LiveTrading]
Name=Live Trading (Real Money)
Exec=bash -c "cd {self.spyder_home} && source ~/.bashrc && python3 spyder_launcher_enhanced.py --mode=live"
Icon={icon_line.split("=")[1]}

[Desktop Action RemoteTWS]
Name=Remote TWS Connection
Exec=bash -c "cd {self.spyder_home} && source ~/.bashrc && python3 spyder_launcher_enhanced.py --connection=remote"
Icon={icon_line.split("=")[1]}

[Desktop Action TestConnection]
Name=Test API Connection
Exec=bash -c "cd {self.spyder_home} && source ~/.bashrc && python3 -c 'from spyder_launcher_enhanced import *; app = SpyderEnhancedLauncher(); app.test_connection()'"
Icon={icon_line.split("=")[1]}

[Desktop Action NuclearRestart]
Name=Nuclear Restart Gateway
Exec=bash -c "source ~/.bashrc && gateway-nuclear-restart"
Icon={icon_line.split("=")[1]}
"""

        # Write desktop file
        try:
            with open(self.desktop_file, "w") as f:
                f.write(desktop_content)
            print(f"✅ Desktop file created: {self.desktop_file}")
            return True
        except Exception as e:
            print(f"❌ Error creating desktop file: {e}")
            return False

    def make_executable(self):
        """Make the desktop file executable"""
        print("🔧 Setting executable permissions...")

        try:
            os.chmod(self.desktop_file, 0o755)
            print("✅ Permissions set successfully")
            return True
        except Exception as e:
            print(f"❌ Error setting permissions: {e}")
            return False

    def update_desktop_database(self):
        """Update the desktop database"""
        print("🔄 Updating desktop database...")

        try:
            subprocess.run(
                ["update-desktop-database", str(self.desktop_dir)],
                capture_output=True,
                check=False,
            )
            print("✅ Desktop database updated")
            return True
        except Exception as e:
            print(f"⚠️  Could not update desktop database: {e}")
            print("   (This is non-critical - launcher will still work)")
            return True

    def install_to_desktop(self):
        """Optionally install to desktop for quick access"""
        print()
        print("📋 Desktop Shortcut Installation")
        print("-" * 40)
        print("Would you like to create a shortcut on your desktop?")
        print("This allows quick access to SPYDER from your desktop.")
        print()

        try:
            desktop_path = self.home / "Desktop"
            if not desktop_path.exists():
                print("⚠️  Desktop folder not found - skipping desktop shortcut")
                return True

            desktop_shortcut = desktop_path / "spyder-trading.desktop"

            # Copy desktop file to Desktop
            import shutil

            shutil.copy2(self.desktop_file, desktop_shortcut)
            os.chmod(desktop_shortcut, 0o755)

            print(f"✅ Desktop shortcut created: {desktop_shortcut}")
            return True

        except Exception as e:
            print(f"⚠️  Could not create desktop shortcut: {e}")
            return True  # Non-critical

    def show_completion_message(self):
        """Show installation completion message"""
        print()
        print("=" * 70)
        print("✅ SPYDER DESKTOP LAUNCHER INSTALLED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("🚀 HOW TO LAUNCH SPYDER:")
        print()
        print("1. From Applications Menu:")
        print("   • Open your applications menu")
        print("   • Search for 'SPYDER' or 'Trading'")
        print("   • Click the SPYDER Trading System icon")
        print()
        print("2. Right-Click Options:")
        print("   • Right-click the SPYDER icon in applications menu")
        print("   • Choose from:")
        print("     - Paper Trading (Safe)")
        print("     - Live Trading (Real Money)")
        print("     - Remote TWS Connection")
        print("     - Test API Connection")
        print("     - Nuclear Restart Gateway")
        print()
        print("3. From Desktop Shortcut:")
        print("   • Double-click the SPYDER icon on your desktop")
        print()
        print("4. Command Line (Alternative):")
        print("   • Open terminal and run: spyder-launch")
        print()
        print("🎯 LAUNCHER FEATURES:")
        print("   ✅ Enhanced GUI with dual-mode support")
        print("   ✅ Local Gateway + Remote TWS selection")
        print("   ✅ Paper + Live trading mode switching")
        print("   ✅ Real-time connection status monitoring")
        print("   ✅ Nuclear restart integration")
        print("   ✅ Professional right-click context menu")
        print()
        print("🔧 CONFIGURATION:")
        print(f"   Launcher: {self.spyder_home}/spyder_launcher_enhanced.py")
        print(f"   Icon: {self.icon_path if self.icon_path else 'System default'}")
        print(f"   Desktop File: {self.desktop_file}")
        print()
        print("💡 TIP: You can customize the launcher by editing:")
        print(f"   {self.desktop_file}")
        print()
        print("🎉 Your professional trading system is ready to launch!")
        print()

    def run_installation(self):
        """Run the complete installation process"""
        self.print_header()

        # Check prerequisites
        if not self.check_prerequisites():
            print()
            print("❌ Prerequisites check failed!")
            print("   Please ensure SPYDER is properly installed.")
            return False

        # Create desktop file
        if not self.create_desktop_file():
            return False

        # Make executable
        if not self.make_executable():
            return False

        # Update database
        self.update_desktop_database()

        # Install to desktop
        self.install_to_desktop()

        # Show completion message
        self.show_completion_message()

        return True


def main():
    """Main entry point"""
    try:
        installer = SpyderDesktopInstaller()
        success = installer.run_installation()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Installation interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Installation error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
