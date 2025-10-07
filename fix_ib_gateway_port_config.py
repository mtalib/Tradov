#!/usr/bin/env python3
"""
IB Gateway Port Configuration Fix
=================================

This script fixes the port configuration mismatch in IB Gateway where the
LocalServerPort setting doesn't match the actual trading mode (paper/live).

The script will:
1. Detect current trading mode from configuration
2. Set correct LocalServerPort based on trading mode
3. Backup original configuration before changes
4. Verify the fix by checking actual listening ports

Port mappings:
- Paper Trading: Port 4002 (LocalServerPort=4002)
- Live Trading: Port 4001 (LocalServerPort=4001)

Usage:
    python fix_ib_gateway_port_config.py
    python fix_ib_gateway_port_config.py --dry-run
    python fix_ib_gateway_port_config.py --trading-mode paper
    python fix_ib_gateway_port_config.py --trading-mode live
"""

import os
import sys
import shutil
import subprocess
import re
from datetime import datetime
from pathlib import Path
import argparse


class IBGatewayPortConfigFix:
    """Fix IB Gateway port configuration to match trading mode"""

    def __init__(self, dry_run=False, force_trading_mode=None):
        self.dry_run = dry_run
        self.force_trading_mode = force_trading_mode
        self.jts_ini_path = None
        self.backup_path = None
        self.current_config = {}
        self.recommended_port = None
        self.current_trading_mode = None

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

        # Common locations
        possible_paths = [
            Path.home() / "Jts" / "jts.ini",
            Path.home() / ".wine" / "drive_c" / "Jts" / "jts.ini",
        ]

        # Search with find command
        try:
            result = subprocess.run(
                ["find", str(Path.home()), "-name", "jts.ini", "-type", "f"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and "Trash" not in line and "Backup" not in line:
                        possible_paths.append(Path(line))
        except:
            pass

        # Find active configuration
        for path in possible_paths:
            if path.exists() and path.is_file():
                try:
                    with open(path, "r") as f:
                        content = f.read()
                        if "[IBGateway]" in content:
                            self.jts_ini_path = path
                            self.log_success(f"Found jts.ini: {path}")
                            return True
                except:
                    continue

        self.log_error("Could not locate jts.ini file")
        return False

    def read_current_config(self):
        """Read current jts.ini configuration"""
        self.log_info("Reading current configuration...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Parse configuration
            current_section = None
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Section header
                if line.startswith("[") and line.endswith("]"):
                    current_section = line[1:-1]
                    if current_section not in self.current_config:
                        self.current_config[current_section] = {}
                    continue

                # Key-value pair
                if "=" in line and current_section:
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    self.current_config[current_section][key] = value

            return True

        except Exception as e:
            self.log_error(f"Failed to read configuration: {e}")
            return False

    def analyze_trading_mode(self):
        """Analyze current trading mode and determine correct port"""
        self.log_info("Analyzing trading mode configuration...")

        # Get trading mode indicators
        ibgateway_section = self.current_config.get("IBGateway", {})
        logon_section = self.current_config.get("Logon", {})

        trading_mode_1 = ibgateway_section.get("TradingMode", "").lower()
        trading_mode_2 = logon_section.get("tradingMode", "").lower()

        # Determine current trading mode
        if self.force_trading_mode:
            self.current_trading_mode = self.force_trading_mode
            self.log_info(f"Forced trading mode: {self.current_trading_mode}")
        elif trading_mode_1 == "paper" or trading_mode_2 == "p":
            self.current_trading_mode = "paper"
            self.log_info("Detected trading mode: Paper Trading")
        elif trading_mode_1 == "live" or trading_mode_2 == "l":
            self.current_trading_mode = "live"
            self.log_info("Detected trading mode: Live Trading")
        else:
            self.log_warning("Could not determine trading mode, defaulting to paper")
            self.current_trading_mode = "paper"

        # Set recommended port based on trading mode
        if self.current_trading_mode == "paper":
            self.recommended_port = 4002
        else:
            self.recommended_port = 4001

        # Check current LocalServerPort setting
        current_port = ibgateway_section.get("LocalServerPort")
        if current_port:
            current_port = int(current_port)
            self.log_info(f"Current LocalServerPort: {current_port}")
            self.log_info(f"Recommended LocalServerPort: {self.recommended_port}")

            if current_port == self.recommended_port:
                self.log_success("Port configuration is already correct!")
                return "already_correct"
            else:
                self.log_warning(
                    f"Port mismatch: configured {current_port}, should be {self.recommended_port}"
                )
                return "needs_fix"
        else:
            self.log_warning("No LocalServerPort setting found")
            return "missing_setting"

    def check_actual_listening_ports(self):
        """Check what ports IB Gateway is actually listening on"""
        self.log_info("Checking actual listening ports...")

        try:
            result = subprocess.run(
                ["netstat", "-tlnp"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                listening_ports = []
                for line in result.stdout.split("\n"):
                    for port in [4001, 4002, 7496, 7497]:
                        if f":{port}" in line and "LISTEN" in line and "java" in line:
                            listening_ports.append(port)

                if listening_ports:
                    self.log_success(
                        f"IB Gateway listening on ports: {listening_ports}"
                    )

                    # Check if recommended port is listening
                    if self.recommended_port in listening_ports:
                        self.log_success(
                            f"Recommended port {self.recommended_port} is listening"
                        )
                    else:
                        self.log_warning(
                            f"Recommended port {self.recommended_port} is NOT listening"
                        )

                    return listening_ports
                else:
                    self.log_warning("No IB Gateway ports detected as listening")
                    return []

        except Exception as e:
            self.log_error(f"Failed to check listening ports: {e}")
            return []

    def create_backup(self):
        """Create backup of current configuration"""
        if self.dry_run:
            self.log_info("DRY RUN: Would create backup of jts.ini")
            return True

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = (
            self.jts_ini_path.parent / f"jts.ini.port_fix_backup_{timestamp}"
        )

        try:
            shutil.copy2(self.jts_ini_path, self.backup_path)
            self.log_success(f"Created backup: {self.backup_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to create backup: {e}")
            return False

    def update_port_configuration(self):
        """Update LocalServerPort in configuration"""
        self.log_info(f"Updating LocalServerPort to {self.recommended_port}...")

        if self.dry_run:
            self.log_info(f"DRY RUN: Would set LocalServerPort={self.recommended_port}")
            return True

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Update or add LocalServerPort setting
            if re.search(r"LocalServerPort\s*=", content, re.IGNORECASE):
                # Replace existing setting
                content = re.sub(
                    r"LocalServerPort\s*=.*$",
                    f"LocalServerPort={self.recommended_port}",
                    content,
                    flags=re.MULTILINE | re.IGNORECASE,
                )
            else:
                # Add new setting to [IBGateway] section
                if "[IBGateway]" in content:
                    content = re.sub(
                        r"(\[IBGateway\])",
                        f"\\1\nLocalServerPort={self.recommended_port}",
                        content,
                        count=1,
                    )
                else:
                    # Add new section if needed
                    content = (
                        f"[IBGateway]\nLocalServerPort={self.recommended_port}\n\n"
                        + content
                    )

            # Also ensure trading mode consistency
            if self.current_trading_mode == "paper":
                # Ensure TradingMode=paper in IBGateway section
                if re.search(r"TradingMode\s*=", content, re.IGNORECASE):
                    content = re.sub(
                        r"TradingMode\s*=.*$",
                        "TradingMode=paper",
                        content,
                        flags=re.MULTILINE | re.IGNORECASE,
                    )
                else:
                    content = re.sub(
                        r"(\[IBGateway\])",
                        "\\1\nTradingMode=paper",
                        content,
                        count=1,
                    )

                # Ensure tradingMode=p in Logon section
                if re.search(r"tradingMode\s*=", content, re.IGNORECASE):
                    content = re.sub(
                        r"tradingMode\s*=.*$",
                        "tradingMode=p",
                        content,
                        flags=re.MULTILINE | re.IGNORECASE,
                    )

            elif self.current_trading_mode == "live":
                # Ensure TradingMode=live in IBGateway section
                if re.search(r"TradingMode\s*=", content, re.IGNORECASE):
                    content = re.sub(
                        r"TradingMode\s*=.*$",
                        "TradingMode=live",
                        content,
                        flags=re.MULTILINE | re.IGNORECASE,
                    )
                else:
                    content = re.sub(
                        r"(\[IBGateway\])",
                        "\\1\nTradingMode=live",
                        content,
                        count=1,
                    )

                # Ensure tradingMode=l in Logon section
                if re.search(r"tradingMode\s*=", content, re.IGNORECASE):
                    content = re.sub(
                        r"tradingMode\s*=.*$",
                        "tradingMode=l",
                        content,
                        flags=re.MULTILINE | re.IGNORECASE,
                    )

            # Write updated content
            with open(self.jts_ini_path, "w") as f:
                f.write(content)

            self.log_success("Configuration updated successfully")
            return True

        except Exception as e:
            self.log_error(f"Failed to update configuration: {e}")
            return False

    def verify_configuration(self):
        """Verify the updated configuration"""
        self.log_info("Verifying updated configuration...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Check LocalServerPort
            port_match = re.search(
                r"LocalServerPort\s*=\s*(\d+)", content, re.IGNORECASE
            )
            if port_match:
                configured_port = int(port_match.group(1))
                if configured_port == self.recommended_port:
                    self.log_success(
                        f"LocalServerPort correctly set to {configured_port}"
                    )
                    return True
                else:
                    self.log_error(
                        f"LocalServerPort is {configured_port}, expected {self.recommended_port}"
                    )
                    return False
            else:
                self.log_error("LocalServerPort setting not found in updated file")
                return False

        except Exception as e:
            self.log_error(f"Configuration verification failed: {e}")
            return False

    def run_port_config_fix(self):
        """Run the complete port configuration fix process"""
        print("🔧 IB Gateway Port Configuration Fix")
        print("=" * 50)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        if self.force_trading_mode:
            print(f"Forced Trading Mode: {self.force_trading_mode}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # Step 1: Find jts.ini
        if not self.find_jts_ini():
            return False

        # Step 2: Read current configuration
        if not self.read_current_config():
            return False

        # Step 3: Analyze trading mode and ports
        analysis_result = self.analyze_trading_mode()

        if analysis_result == "already_correct":
            self.log_success("Port configuration is already correct!")

            # Still check actual listening ports for verification
            self.check_actual_listening_ports()

            print("\n" + "=" * 50)
            print("✅ NO CHANGES NEEDED")
            print("=" * 50)
            print(f"🎯 Trading Mode: {self.current_trading_mode.title()}")
            print(f"🔌 LocalServerPort: {self.recommended_port} (correct)")
            print("\n💡 NEXT STEPS:")
            print("   • Configuration is correct - no changes needed")
            print("   • If connections still fail, check other API settings")
            print("   • Verify 'Enable ActiveX and Socket Clients' in IB Gateway GUI")
            return True

        # Step 4: Check actual listening ports
        listening_ports = self.check_actual_listening_ports()

        # Step 5: Create backup
        if not self.create_backup():
            return False

        # Step 6: Update configuration
        if not self.update_port_configuration():
            return False

        # Step 7: Verify configuration
        if not self.verify_configuration():
            self.log_warning("Verification failed, but configuration was updated")

        # Success message
        print("\n" + "=" * 50)
        print("✅ PORT CONFIGURATION UPDATED SUCCESSFULLY")
        print("=" * 50)
        print(f"📁 Configuration file: {self.jts_ini_path}")
        if not self.dry_run:
            print(f"💾 Backup created: {self.backup_path}")
        print(f"🎯 Trading Mode: {self.current_trading_mode.title()}")
        print(f"🔌 LocalServerPort: {self.recommended_port}")

        print("\n🔄 NEXT STEPS:")
        print("   1. Restart IB Gateway to apply the new port configuration")
        print("   2. Verify IB Gateway listens on the correct port after restart")
        print("   3. Test API connections using the correct port")
        print("   4. Check IB Gateway GUI settings if connections still fail")

        if listening_ports:
            print(f"\n📊 Current Listening Ports: {listening_ports}")
            if self.recommended_port not in listening_ports:
                print(
                    f"   ⚠️ Restart required: IB Gateway not yet listening on port {self.recommended_port}"
                )

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Fix IB Gateway Port Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fix_ib_gateway_port_config.py                    # Auto-detect mode and fix
  python fix_ib_gateway_port_config.py --dry-run         # Preview changes only
  python fix_ib_gateway_port_config.py --trading-mode paper  # Force paper trading mode
  python fix_ib_gateway_port_config.py --trading-mode live   # Force live trading mode

Port Mappings:
  Paper Trading: Port 4002
  Live Trading:  Port 4001
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying them"
    )
    parser.add_argument(
        "--trading-mode",
        choices=["paper", "live"],
        help="Force specific trading mode (paper or live)",
    )

    args = parser.parse_args()

    try:
        fixer = IBGatewayPortConfigFix(
            dry_run=args.dry_run, force_trading_mode=args.trading_mode
        )

        success = fixer.run_port_config_fix()
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
