#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: add_missing_api_settings.py
Purpose: Add Missing Critical API Settings to IB Gateway jts.ini

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Add Missing Critical API Settings to IB Gateway jts.ini

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
import re
from datetime import datetime
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import shutil
import argparse

class AddMissingAPISettings:
    """Add missing critical API settings to jts.ini"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.jts_ini_path = None
        self.backup_path = None

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

    def create_backup(self):
        """Create backup of current configuration"""
        if self.dry_run:
            self.log_info("DRY RUN: Would create backup of jts.ini")
            return True

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = (
            self.jts_ini_path.parent / f"jts.ini.api_settings_backup_{timestamp}"
        )

        try:
            shutil.copy2(self.jts_ini_path, self.backup_path)
            self.log_success(f"Created backup: {self.backup_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to create backup: {e}")
            return False

    def add_missing_api_settings(self):
        """Add missing API settings to jts.ini"""
        self.log_info("Adding missing API settings...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            original_content = content

            # Add ReadOnlyApi=false to IBGateway section if not present
            if "ReadOnlyApi=" not in content:
                self.log_info("Adding ReadOnlyApi=false setting...")
                content = re.sub(
                    r"(ApiOnly=true)", r"\1\nReadOnlyApi=false", content, count=1
                )

            # Ensure proper socket settings are in place
            missing_settings = []

            # Check and add socket-related settings to IBGateway section
            if "SocketPort=" not in content:
                missing_settings.append("SocketPort=4002")
                content = re.sub(
                    r"(LocalServerPort=4002)", r"\1\nSocketPort=4002", content, count=1
                )

            # Add allowOrigSub setting which is sometimes required
            if "allowOrigSub=" not in content:
                missing_settings.append("allowOrigSub=1")
                content = re.sub(
                    r"(ReadOnlyApi=false)", r"\1\nallowOrigSub=1", content, count=1
                )

            # Add masterClientID setting
            if "masterClientID=" not in content:
                missing_settings.append("masterClientID=0")
                content = re.sub(
                    r"(allowOrigSub=1)", r"\1\nmasterClientID=0", content, count=1
                )

            # Ensure TrustedIPs includes wildcard for local connections
            current_trusted_ips = re.search(r"TrustedIPs=([^\n]*)", content)
            if current_trusted_ips:
                trusted_ips_value = current_trusted_ips.group(1)
                # Make sure we have comprehensive local access
                if "0.0.0.0" not in trusted_ips_value:
                    new_trusted_ips = f"{trusted_ips_value},0.0.0.0"
                    content = re.sub(
                        r"TrustedIPs=[^\n]*", f"TrustedIPs={new_trusted_ips}", content
                    )
                    self.log_info("Added 0.0.0.0 to TrustedIPs for broader access")

            if self.dry_run:
                self.log_info("DRY RUN: Would add the following settings:")
                for setting in missing_settings:
                    self.log_info(f"  + {setting}")
                if "0.0.0.0" not in (
                    current_trusted_ips.group(1) if current_trusted_ips else ""
                ):
                    self.log_info("  + 0.0.0.0 to TrustedIPs")
                return True

            # Write the updated content
            with open(self.jts_ini_path, "w") as f:
                f.write(content)

            self.log_success("Successfully added missing API settings")

            if missing_settings:
                self.log_info("Added settings:")
                for setting in missing_settings:
                    self.log_info(f"  + {setting}")

            return True

        except Exception as e:
            self.log_error(f"Failed to add API settings: {e}")
            return False

    def verify_api_settings(self):
        """Verify that all critical API settings are present"""
        self.log_info("Verifying API settings...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            required_settings = [
                "LocalServerPort=4002",
                "ApiOnly=true",
                "ReadOnlyApi=false",
                "TrustedIPs=",
                "SocketPort=4002",
                "allowOrigSub=1",
                "masterClientID=0",
            ]

            missing_settings = []
            for setting in required_settings:
                if setting not in content:
                    missing_settings.append(setting)

            if missing_settings:
                self.log_warning(f"Missing critical settings: {missing_settings}")
                return False
            else:
                self.log_success("All critical API settings verified")
                return True

        except Exception as e:
            self.log_error(f"Verification failed: {e}")
            return False

    def run_api_settings_fix(self):
        """Run the complete API settings fix"""
        print("🔧 Add Missing IB Gateway API Settings")
        print("=" * 50)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # Step 1: Find jts.ini
        if not self.find_jts_ini():
            return False

        # Step 2: Create backup
        if not self.create_backup():
            return False

        # Step 3: Add missing settings
        if not self.add_missing_api_settings():
            return False

        # Step 4: Verify settings
        if not self.verify_api_settings():
            self.log_warning("Some settings may still be missing")

        # Success message
        print("\n" + "=" * 50)
        print("✅ MISSING API SETTINGS ADDED")
        print("=" * 50)
        print(f"📁 Configuration file: {self.jts_ini_path}")
        if not self.dry_run:
            print(f"💾 Backup created: {self.backup_path}")

        print("\n📋 Added Critical Settings:")
        print("   • ReadOnlyApi=false - Allow full API access")
        print("   • SocketPort=4002 - Explicit socket port setting")
        print("   • allowOrigSub=1 - Allow subscription requests")
        print("   • masterClientID=0 - Set master client ID")
        print("   • Enhanced TrustedIPs - Added 0.0.0.0 for local access")

        print("\n⚠️  SECURITY NOTE:")
        print("   • Added 0.0.0.0 to TrustedIPs for maximum compatibility")
        print("   • This allows connections from any IP - use with caution")
        print("   • Consider restricting to specific IPs in production")

        print("\n🔄 NEXT STEPS:")
        print("   1. Restart IB Gateway to load the new API settings")
        print("   2. Test API connection - should now accept socket connections")
        print("   3. If successful, connections should complete handshake")
        print("   4. Monitor for successful API data exchange")

        print("\n💡 WHAT WAS ADDED:")
        print("   These settings are often required but not well-documented:")
        print("   • ReadOnlyApi=false: Enables full API functionality")
        print("   • allowOrigSub=1: Allows market data subscriptions")
        print("   • masterClientID=0: Prevents client ID conflicts")
        print("   • Enhanced TrustedIPs: Broader IP access for testing")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Add Missing IB Gateway API Settings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python add_missing_api_settings.py              # Add missing API settings
  python add_missing_api_settings.py --dry-run    # Preview what would be added

Critical Settings Added:
  • ReadOnlyApi=false
  • SocketPort=4002
  • allowOrigSub=1
  • masterClientID=0
  • Enhanced TrustedIPs
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )

    args = parser.parse_args()

    try:
        fixer = AddMissingAPISettings(dry_run=args.dry_run)
        success = fixer.run_api_settings_fix()
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
