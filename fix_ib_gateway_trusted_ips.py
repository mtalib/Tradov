#!/usr/bin/env python3
"""
IB Gateway Trusted IPs Configuration Fix
========================================

This script fixes the IB Gateway jts.ini configuration to include the correct
trusted IP addresses for your Linux trading system.

The script will:
1. Locate the jts.ini file
2. Backup the current configuration
3. Add the system's IP addresses to the TrustedIPs setting
4. Verify the configuration changes

Usage:
    python fix_ib_gateway_trusted_ips.py
    python fix_ib_gateway_trusted_ips.py --dry-run
    python fix_ib_gateway_trusted_ips.py --restore-backup
"""

import os
import sys
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path
import argparse
import re


class IBGatewayTrustedIPsFix:
    """Fix IB Gateway trusted IPs configuration"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.jts_ini_path = None
        self.backup_path = None
        self.current_ips = []
        self.system_ips = []

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

        # Common locations for IB Gateway configuration
        possible_paths = [
            Path.home() / "Jts" / "jts.ini",
            Path.home() / ".wine" / "drive_c" / "Jts" / "jts.ini",
            Path("/opt/ibgateway/Jts/jts.ini"),
            Path("/usr/local/ibgateway/Jts/jts.ini"),
        ]

        # Also search using find command
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

        # Find the most likely active configuration
        for path in possible_paths:
            if path.exists() and path.is_file():
                # Check if this looks like an active configuration
                try:
                    with open(path, "r") as f:
                        content = f.read()
                        if "[IBGateway]" in content or "[Api]" in content:
                            self.jts_ini_path = path
                            self.log_success(f"Found jts.ini: {path}")
                            return True
                except:
                    continue

        self.log_error("Could not locate jts.ini file")
        return False

    def get_system_ip_addresses(self):
        """Get all relevant IP addresses for this system"""
        self.log_info("Detecting system IP addresses...")

        ip_addresses = set()

        # Always include localhost
        ip_addresses.add("127.0.0.1")

        # Get IP addresses using hostname command
        try:
            result = subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for ip in result.stdout.strip().split():
                    if ip and self._is_valid_ip(ip):
                        ip_addresses.add(ip)
        except:
            pass

        # Get IP addresses using ip command
        try:
            result = subprocess.run(
                ["ip", "addr", "show"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "inet " in line and "scope global" in line:
                        match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
                        if match:
                            ip = match.group(1)
                            if self._is_valid_ip(ip):
                                ip_addresses.add(ip)
        except:
            pass

        # Get primary network interface IP
        try:
            # Connect to a remote address to determine the local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if self._is_valid_ip(local_ip):
                    ip_addresses.add(local_ip)
        except:
            pass

        # Filter out Docker and other virtual interfaces we don't need
        filtered_ips = set()
        for ip in ip_addresses:
            if (
                not ip.startswith("172.17.")  # Docker default
                and not ip.startswith("172.18.")  # Docker networks
                and not ip.startswith("172.19.")  # Docker networks
                and not ip.startswith("169.254.")  # Link-local
            ):
                filtered_ips.add(ip)

        # Always keep at least localhost and primary IP
        if not filtered_ips:
            filtered_ips = ip_addresses

        self.system_ips = sorted(list(filtered_ips))

        self.log_success(f"Detected IP addresses: {', '.join(self.system_ips)}")
        return True

    def _is_valid_ip(self, ip):
        """Validate IP address format"""
        try:
            socket.inet_aton(ip)
            return True
        except:
            return False

    def read_current_config(self):
        """Read current jts.ini configuration"""
        self.log_info("Reading current jts.ini configuration...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Parse TrustedIPs setting
            trusted_ips_match = re.search(
                r"TrustedIPs\s*=\s*(.*)$", content, re.MULTILINE | re.IGNORECASE
            )

            if trusted_ips_match:
                trusted_ips_str = trusted_ips_match.group(1).strip()
                if trusted_ips_str:
                    # Split by comma or semicolon, clean up
                    self.current_ips = [
                        ip.strip()
                        for ip in re.split(r"[,;]", trusted_ips_str)
                        if ip.strip()
                    ]
                else:
                    self.current_ips = []

                self.log_info(f"Current TrustedIPs: {', '.join(self.current_ips)}")
            else:
                self.log_warning("No TrustedIPs setting found in configuration")
                self.current_ips = []

            return True

        except Exception as e:
            self.log_error(f"Failed to read jts.ini: {e}")
            return False

    def create_backup(self):
        """Create backup of current configuration"""
        if self.dry_run:
            self.log_info("DRY RUN: Would create backup of jts.ini")
            return True

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_path = self.jts_ini_path.parent / f"jts.ini.backup_{timestamp}"

        try:
            shutil.copy2(self.jts_ini_path, self.backup_path)
            self.log_success(f"Created backup: {self.backup_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to create backup: {e}")
            return False

    def update_trusted_ips(self):
        """Update TrustedIPs configuration"""
        self.log_info("Updating TrustedIPs configuration...")

        # Combine current IPs with system IPs, removing duplicates
        all_ips = set(self.current_ips + self.system_ips)

        # Remove any invalid or unwanted IPs
        valid_ips = []
        for ip in all_ips:
            if self._is_valid_ip(ip):
                valid_ips.append(ip)

        # Sort for consistent output
        valid_ips.sort()
        new_trusted_ips = ",".join(valid_ips)

        if self.dry_run:
            self.log_info("DRY RUN: Would update TrustedIPs configuration")
            self.log_info(f"DRY RUN: New TrustedIPs = {new_trusted_ips}")
            return True

        try:
            # Read current file content
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Update or add TrustedIPs setting
            if re.search(r"TrustedIPs\s*=", content, re.IGNORECASE):
                # Replace existing setting
                content = re.sub(
                    r"TrustedIPs\s*=.*$",
                    f"TrustedIPs={new_trusted_ips}",
                    content,
                    flags=re.MULTILINE | re.IGNORECASE,
                )
            else:
                # Add new setting to [IBGateway] section
                if "[IBGateway]" in content:
                    content = re.sub(
                        r"(\[IBGateway\])",
                        f"\\1\nTrustedIPs={new_trusted_ips}",
                        content,
                        count=1,
                    )
                else:
                    # Add new section if needed
                    content = f"[IBGateway]\nTrustedIPs={new_trusted_ips}\n\n" + content

            # Write updated content
            with open(self.jts_ini_path, "w") as f:
                f.write(content)

            self.log_success("Updated jts.ini configuration")
            self.log_success(f"New TrustedIPs: {new_trusted_ips}")
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

            # Check that our IPs are present
            for ip in self.system_ips:
                if ip not in content:
                    self.log_warning(f"IP {ip} not found in updated configuration")
                    return False

            self.log_success("Configuration verification passed")
            return True

        except Exception as e:
            self.log_error(f"Configuration verification failed: {e}")
            return False

    def restore_backup(self, backup_file=None):
        """Restore configuration from backup"""
        if backup_file:
            backup_path = Path(backup_file)
        else:
            # Find most recent backup
            backup_dir = self.jts_ini_path.parent
            backups = list(backup_dir.glob("jts.ini.backup_*"))
            if not backups:
                self.log_error("No backup files found")
                return False
            backup_path = max(backups, key=os.path.getctime)

        if not backup_path.exists():
            self.log_error(f"Backup file not found: {backup_path}")
            return False

        try:
            shutil.copy2(backup_path, self.jts_ini_path)
            self.log_success(f"Restored configuration from {backup_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to restore backup: {e}")
            return False

    def run_fix(self):
        """Run the complete trusted IPs fix process"""
        print("🔧 IB Gateway Trusted IPs Configuration Fix")
        print("=" * 50)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # Step 1: Find jts.ini file
        if not self.find_jts_ini():
            return False

        # Step 2: Get system IP addresses
        if not self.get_system_ip_addresses():
            return False

        # Step 3: Read current configuration
        if not self.read_current_config():
            return False

        # Step 4: Check if update is needed
        missing_ips = []
        for ip in self.system_ips:
            if ip not in self.current_ips:
                missing_ips.append(ip)

        if not missing_ips:
            self.log_success("All system IPs are already in TrustedIPs configuration")
            return True

        self.log_info(f"Need to add IPs: {', '.join(missing_ips)}")

        # Step 5: Create backup
        if not self.create_backup():
            return False

        # Step 6: Update configuration
        if not self.update_trusted_ips():
            return False

        # Step 7: Verify configuration
        if not self.verify_configuration():
            self.log_warning("Verification failed, but configuration was updated")

        # Final success message
        print("\n" + "=" * 50)
        print("✅ TRUSTED IPS CONFIGURATION UPDATED SUCCESSFULLY")
        print("=" * 50)
        print(f"📁 Configuration file: {self.jts_ini_path}")
        print(f"💾 Backup created: {self.backup_path}")
        print(f"🌐 Trusted IPs now include: {', '.join(self.system_ips)}")
        print("\n🔄 NEXT STEPS:")
        print("   1. Restart IB Gateway to apply the new configuration")
        print("   2. Test API connection from your trading system")
        print("   3. Monitor IB Gateway logs for connection acceptance")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Fix IB Gateway Trusted IPs Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fix_ib_gateway_trusted_ips.py                    # Apply the fix
  python fix_ib_gateway_trusted_ips.py --dry-run         # Preview changes only
  python fix_ib_gateway_trusted_ips.py --restore-backup  # Restore from backup
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying them"
    )
    parser.add_argument(
        "--restore-backup",
        nargs="?",
        const=True,
        help="Restore from backup (optionally specify backup file)",
    )

    args = parser.parse_args()

    try:
        fixer = IBGatewayTrustedIPsFix(dry_run=args.dry_run)

        if args.restore_backup:
            if not fixer.find_jts_ini():
                sys.exit(1)

            backup_file = (
                args.restore_backup if isinstance(args.restore_backup, str) else None
            )
            success = fixer.restore_backup(backup_file)
            sys.exit(0 if success else 1)

        success = fixer.run_fix()
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
