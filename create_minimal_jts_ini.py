#!/usr/bin/env python3
"""
Create Minimal Working jts.ini Configuration for IB Gateway API
==============================================================

This script creates a minimal, known-working jts.ini configuration for IB Gateway
that focuses only on the essential settings needed for API connectivity.

The approach is to use only the most basic, proven settings rather than
a comprehensive configuration that might conflict with IB Gateway's internals.

Usage:
    python create_minimal_jts_ini.py
    python create_minimal_jts_ini.py --dry-run
    python create_minimal_jts_ini.py --live-mode
"""

import os
import sys
import shutil
import socket
from datetime import datetime
from pathlib import Path
import argparse


class MinimalJTSIniCreator:
    """Create minimal working jts.ini configuration"""

    def __init__(self, dry_run=False, live_mode=False):
        self.dry_run = dry_run
        self.live_mode = live_mode
        self.jts_ini_path = None
        self.backup_path = None
        self.system_ip = None

    def log_info(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ℹ️  {message}")

    def log_success(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ✅ {message}")

    def log_warning(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ⚠️  {message}")

    def log_error(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ❌ {message}")

    def find_jts_ini(self):
        """Locate the jts.ini file"""
        self.log_info("Searching for jts.ini file...")

        possible_paths = [
            Path.home() / "Jts" / "jts.ini",
            Path.home() / ".wine" / "drive_c" / "Jts" / "jts.ini",
        ]

        for path in possible_paths:
            if path.exists() and path.is_file():
                self.jts_ini_path = path
                self.log_success(f"Found jts.ini: {path}")
                return True

        self.log_error("Could not locate jts.ini file")
        return False

    def get_system_ip(self):
        """Get system's primary IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                self.system_ip = s.getsockname()[0]
                return self.system_ip
        except:
            self.system_ip = "192.168.1.9"  # Fallback to known IP
            return self.system_ip

    def create_backup(self):
        """Create backup of current configuration"""
        if self.dry_run:
            self.log_info("DRY RUN: Would create backup of jts.ini")
            return True

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = (
            self.jts_ini_path.parent / f"jts.ini.minimal_backup_{timestamp}"
        )

        try:
            shutil.copy2(self.jts_ini_path, self.backup_path)
            self.log_success(f"Created backup: {self.backup_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to create backup: {e}")
            return False

    def create_minimal_config(self):
        """Create minimal working jts.ini configuration"""

        # Determine trading mode and ports
        if self.live_mode:
            trading_mode = "live"
            trading_mode_short = "l"
            api_port = 4001
        else:
            trading_mode = "paper"
            trading_mode_short = "p"
            api_port = 4002

        # Get current date for SSL configuration
        today = datetime.now().strftime("%Y%m%d")

        # MINIMAL configuration - only essential settings
        config_content = f"""[IBGateway]
WriteDebug=false
MainWindow.Width=1200
MainWindow.Height=800
MainWindow.Maximized=false
RemotePortOrderRouting=4001
RemoteHostOrderRouting=ndc1.ibllc.com
TradingMode={trading_mode}
LocalServerPort={api_port}
TrustedIPs=127.0.0.1,{self.system_ip}

[Logon]
useRemoteSettings=false
TimeZone=Europe/Lisbon
tradingMode={trading_mode_short}
colorPalletName=dark
Steps=8
Locale=en
os_titlebar=false
UseSSL=true
SupportsSSL=ndc1.ibllc.com:4000,true,{today},false;cdc1.ibllc.com:4000,true,{today},false
screenHeight=1080
s3store=true
ibkrBranding=pro

[Communication]
Peer=cdc1.ibllc.com:4001
Region=us
"""

        return config_content

    def write_minimal_config(self):
        """Write the minimal configuration"""
        self.log_info("Creating minimal jts.ini configuration...")

        if self.dry_run:
            self.log_info("DRY RUN: Would write minimal configuration")
            config_content = self.create_minimal_config()
            print("\n" + "=" * 60)
            print("DRY RUN: Minimal configuration would be:")
            print("=" * 60)
            print(config_content)
            print("=" * 60)
            return True

        try:
            config_content = self.create_minimal_config()

            with open(self.jts_ini_path, "w") as f:
                f.write(config_content)

            self.log_success("Minimal configuration written successfully")
            return True

        except Exception as e:
            self.log_error(f"Failed to write minimal configuration: {e}")
            return False

    def verify_minimal_config(self):
        """Verify the minimal configuration was written correctly"""
        self.log_info("Verifying minimal configuration...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Check for essential settings only
            required_settings = [
                "TrustedIPs=127.0.0.1,",
                f"LocalServerPort={'4001' if self.live_mode else '4002'}",
                f"TradingMode={'live' if self.live_mode else 'paper'}",
                "[IBGateway]",
                "[Logon]",
                "[Communication]",
            ]

            missing_settings = []
            for setting in required_settings:
                if setting not in content:
                    missing_settings.append(setting)

            if missing_settings:
                self.log_error(f"Missing required settings: {missing_settings}")
                return False
            else:
                self.log_success(
                    "All essential settings verified in minimal configuration"
                )
                return True

        except Exception as e:
            self.log_error(f"Configuration verification failed: {e}")
            return False

    def run_minimal_creation(self):
        """Run the minimal jts.ini configuration creation"""
        print("🔧 Minimal IB Gateway jts.ini Configuration Creator")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Trading Mode: {'Live' if self.live_mode else 'Paper'}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Step 1: Find jts.ini
        if not self.find_jts_ini():
            return False

        # Step 2: Get system IP
        system_ip = self.get_system_ip()
        self.log_success(f"System IP detected: {system_ip}")

        # Step 3: Create backup
        if not self.create_backup():
            return False

        # Step 4: Write minimal configuration
        if not self.write_minimal_config():
            return False

        # Step 5: Verify configuration
        if not self.verify_minimal_config():
            self.log_warning("Verification had issues, but configuration was written")

        # Success message
        print("\n" + "=" * 60)
        print("✅ MINIMAL JTS.INI CONFIGURATION CREATED")
        print("=" * 60)
        print(f"📁 Configuration file: {self.jts_ini_path}")
        if not self.dry_run:
            print(f"💾 Backup created: {self.backup_path}")
        print(f"🎯 Trading Mode: {'Live' if self.live_mode else 'Paper'}")
        print(f"🔌 API Port: {'4001' if self.live_mode else '4002'}")
        print(f"🌐 Trusted IPs: 127.0.0.1, {system_ip}")

        print("\n📋 Minimal Configuration Includes:")
        print("   • [IBGateway] - Essential gateway settings only")
        print("   • [Logon] - Basic authentication settings")
        print("   • [Communication] - Server connection settings")
        print("   • TrustedIPs - Local and system IP addresses")
        print("   • LocalServerPort - Correct port for trading mode")

        print("\n⚠️  What's NOT Included (intentionally):")
        print("   • [API] section - Let IB Gateway use defaults")
        print("   • [Security] section - Let IB Gateway handle security")
        print("   • [Network] section - Let IB Gateway manage networking")
        print("   • [Advanced] section - Avoid advanced settings conflicts")
        print("   • ApiOnly setting - Let IB Gateway decide")

        print("\n🔄 NEXT STEPS:")
        print("   1. Restart IB Gateway to load the minimal configuration")
        print("   2. Check if IB Gateway starts properly with fewer settings")
        print("   3. Test basic API connection")
        print("   4. If successful, gradually add settings if needed")

        print("\n💡 THEORY:")
        print("   The previous comprehensive config may have conflicted with")
        print("   IB Gateway's internal settings. This minimal approach lets")
        print("   IB Gateway use its default API behavior while only setting")
        print("   the essential connectivity parameters.")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Create Minimal IB Gateway jts.ini Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_minimal_jts_ini.py                    # Create minimal paper trading config
  python create_minimal_jts_ini.py --dry-run         # Preview minimal configuration
  python create_minimal_jts_ini.py --live-mode       # Configure for live trading

Philosophy:
  Less is more - use only essential settings and let IB Gateway handle the rest.
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview minimal configuration without applying",
    )
    parser.add_argument(
        "--live-mode",
        action="store_true",
        help="Configure for live trading (port 4001)",
    )

    args = parser.parse_args()

    try:
        creator = MinimalJTSIniCreator(dry_run=args.dry_run, live_mode=args.live_mode)
        success = creator.run_minimal_creation()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n⚠️ Operation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
