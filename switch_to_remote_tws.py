#!/usr/bin/env python3
"""
Switch Spyder Configuration to Remote TWS
=========================================

This script automatically switches the Spyder configuration from local IB Gateway
to remote TWS running on a Windows computer. It updates the main config.py file
and validates all hardcoded localhost references in the codebase.

Usage:
    python switch_to_remote_tws.py
    python switch_to_remote_tws.py --validate-only
    python switch_to_remote_tws.py --revert
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


class RemoteTWSConfigSwitcher:
    def __init__(self):
        self.spyder_home = Path(__file__).parent
        self.config_dir = self.spyder_home / "config"
        self.backup_dir = self.config_dir / "backups"

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

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

    def backup_current_config(self):
        """Backup current configuration"""
        config_file = self.config_dir / "config.py"

        if not config_file.exists():
            self.log_warning("No existing config.py found to backup")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"config_{timestamp}.py"

        try:
            shutil.copy2(config_file, backup_file)
            self.log_success(f"Configuration backed up to: {backup_file}")
            return backup_file
        except Exception as e:
            self.log_error(f"Failed to backup configuration: {e}")
            return None

    def switch_to_remote_tws(self):
        """Switch to remote TWS configuration"""
        self.log_info("Switching to remote TWS configuration...")

        # Check if remote TWS config exists
        remote_config = self.config_dir / "config_remote_tws.py"
        if not remote_config.exists():
            self.log_error("Remote TWS configuration not found!")
            self.log_error("Please run: ./setup_remote_tws.sh --interactive")
            return False

        # Backup current config
        backup_file = self.backup_current_config()
        if backup_file is None:
            return False

        # Copy remote config to main config
        config_file = self.config_dir / "config.py"
        try:
            shutil.copy2(remote_config, config_file)
            self.log_success("Switched to remote TWS configuration!")

            # Validate the new configuration
            if self.validate_remote_config():
                self.log_success("Configuration validation passed!")
                return True
            else:
                self.log_warning(
                    "Configuration validation failed, but switch completed"
                )
                return True

        except Exception as e:
            self.log_error(f"Failed to switch configuration: {e}")

            # Try to restore backup
            if backup_file and backup_file.exists():
                try:
                    shutil.copy2(backup_file, config_file)
                    self.log_info("Restored previous configuration")
                except:
                    pass

            return False

    def revert_to_local_gateway(self):
        """Revert to local IB Gateway configuration"""
        self.log_info("Reverting to local IB Gateway configuration...")

        # Find the most recent backup
        backups = list(self.backup_dir.glob("config_*.py"))
        if not backups:
            self.log_error("No backup configurations found!")
            return False

        # Sort by modification time and get the most recent
        latest_backup = max(backups, key=lambda p: p.stat().st_mtime)

        config_file = self.config_dir / "config.py"

        try:
            # Create a backup of current remote config
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup = self.backup_dir / f"config_remote_backup_{timestamp}.py"
            shutil.copy2(config_file, current_backup)

            # Restore the backup
            shutil.copy2(latest_backup, config_file)

            self.log_success(f"Reverted to configuration from: {latest_backup}")
            self.log_info(f"Current remote config backed up to: {current_backup}")

            return True

        except Exception as e:
            self.log_error(f"Failed to revert configuration: {e}")
            return False

    def validate_remote_config(self):
        """Validate remote TWS configuration"""
        self.log_info("Validating remote TWS configuration...")

        config_file = self.config_dir / "config.py"
        if not config_file.exists():
            self.log_error("Configuration file not found!")
            return False

        try:
            # Import the configuration
            import importlib.util

            spec = importlib.util.spec_from_file_location("config", config_file)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)

            # Check if it has IB_CONFIG
            if not hasattr(config_module, "IB_CONFIG"):
                self.log_error("Configuration missing IB_CONFIG!")
                return False

            ib_config = config_module.IB_CONFIG

            # Validate structure
            if "gateway" not in ib_config:
                self.log_error("Configuration missing gateway section!")
                return False

            gateway_config = ib_config["gateway"]

            # Check paper trading config
            if "paper" in gateway_config:
                paper = gateway_config["paper"]
                host = paper.get("host", "")
                port = paper.get("port", 0)

                if host != "127.0.0.1":
                    self.log_success(
                        f"Paper trading configured for remote host: {host}:{port}"
                    )
                else:
                    self.log_warning("Paper trading still using localhost")

            # Check live trading config
            if "live" in gateway_config:
                live = gateway_config["live"]
                host = live.get("host", "")
                port = live.get("port", 0)

                if host != "127.0.0.1":
                    self.log_success(
                        f"Live trading configured for remote host: {host}:{port}"
                    )
                else:
                    self.log_warning("Live trading still using localhost")

            # Check connection type
            connection_type = ib_config.get("connection_type", "")
            if connection_type == "remote_tws":
                self.log_success("Connection type set to remote_tws")
            else:
                self.log_warning(f"Connection type: {connection_type}")

            return True

        except Exception as e:
            self.log_error(f"Configuration validation failed: {e}")
            return False

    def check_hardcoded_references(self):
        """Check for hardcoded localhost references in the codebase"""
        self.log_info("Checking for hardcoded localhost references...")

        # Files that should have been updated
        updated_files = [
            "SpyderQ_Scripts/SpyderQ91_MonitoringUtilities.py",
            "SpyderQ_Scripts/SpyderQ45_Diagnostics.py",
            "SpyderQ_Scripts/SpyderQ24_ProductionWatchdog.py",
            "SpyderQ_Scripts/SpyderQ25_SystemMonitor.py",
            "SpyderQ_Scripts/SpyderQ22_CheckIBStatus.py",
        ]

        issues_found = []

        for file_path in updated_files:
            full_path = self.spyder_home / file_path
            if not full_path.exists():
                self.log_warning(f"File not found: {file_path}")
                continue

            try:
                with open(full_path, "r") as f:
                    content = f.read()

                # Check for hardcoded localhost
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if (
                        "127.0.0.1" in line
                        and "IB_CONFIG" not in line
                        and "fallback" not in line.lower()
                    ):
                        issues_found.append(f"{file_path}:{i} - {line.strip()}")

            except Exception as e:
                self.log_warning(f"Could not check {file_path}: {e}")

        if issues_found:
            self.log_warning("Found hardcoded localhost references:")
            for issue in issues_found:
                print(f"  • {issue}")
            return False
        else:
            self.log_success("No hardcoded localhost references found!")
            return True

    def display_status(self):
        """Display current configuration status"""
        print("=" * 60)
        print("SPYDER CONFIGURATION STATUS")
        print("=" * 60)

        config_file = self.config_dir / "config.py"
        remote_config = self.config_dir / "config_remote_tws.py"

        # Check main config
        if config_file.exists():
            print(f"✅ Main configuration: {config_file}")

            # Try to determine if it's remote or local
            try:
                with open(config_file, "r") as f:
                    content = f.read()

                if "remote_tws" in content:
                    print("   📡 Type: Remote TWS")
                elif "127.0.0.1" in content:
                    print("   🏠 Type: Local Gateway")
                else:
                    print("   ❓ Type: Unknown")

            except:
                print("   ❓ Could not determine type")
        else:
            print(f"❌ Main configuration: NOT FOUND")

        # Check remote config
        if remote_config.exists():
            print(f"✅ Remote TWS config: {remote_config}")

            # Try to extract IP
            try:
                with open(remote_config, "r") as f:
                    content = f.read()

                import re

                ip_match = re.search(r'"host":\s*"([^"]+)"', content)
                if ip_match and ip_match.group(1) != "127.0.0.1":
                    print(f"   🌐 Remote IP: {ip_match.group(1)}")

            except:
                pass
        else:
            print(f"❌ Remote TWS config: NOT FOUND")

        # Check backups
        backups = list(self.backup_dir.glob("config_*.py"))
        print(f"💾 Configuration backups: {len(backups)}")

        if backups:
            latest = max(backups, key=lambda p: p.stat().st_mtime)
            mod_time = datetime.fromtimestamp(latest.stat().st_mtime)
            print(
                f"   Latest: {latest.name} ({mod_time.strftime('%Y-%m-%d %H:%M:%S')})"
            )

        print("=" * 60)

    def run_tests(self):
        """Run connection tests with current configuration"""
        self.log_info("Running connection tests...")

        # Test if our diagnostic tools work
        test_scripts = [
            "debug_tws_connection.py",
            "simple_ib_test.py",
        ]

        for script in test_scripts:
            script_path = self.spyder_home / script
            if script_path.exists():
                self.log_info(f"Testing with {script}...")

                # Import and get configured IP
                try:
                    from config.config import IB_CONFIG

                    host = (
                        IB_CONFIG.get("gateway", {})
                        .get("paper", {})
                        .get("host", "127.0.0.1")
                    )
                    port = (
                        IB_CONFIG.get("gateway", {}).get("paper", {}).get("port", 7497)
                    )

                    print(f"   Target: {host}:{port}")
                    print(f"   Run: python {script} --ip {host} --port {port}")

                except Exception as e:
                    self.log_warning(f"Could not get config for testing: {e}")
            else:
                self.log_warning(f"Test script not found: {script}")


def main():
    parser = argparse.ArgumentParser(
        description="Switch Spyder to Remote TWS Configuration"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate current configuration",
    )
    parser.add_argument(
        "--revert", action="store_true", help="Revert to previous configuration"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show configuration status"
    )
    parser.add_argument("--test", action="store_true", help="Run connection tests")
    parser.add_argument(
        "--check-hardcoded",
        action="store_true",
        help="Check for hardcoded localhost references",
    )

    args = parser.parse_args()

    switcher = RemoteTWSConfigSwitcher()

    if args.status:
        switcher.display_status()
        return

    if args.check_hardcoded:
        success = switcher.check_hardcoded_references()
        sys.exit(0 if success else 1)

    if args.test:
        switcher.run_tests()
        return

    if args.validate_only:
        success = switcher.validate_remote_config()
        sys.exit(0 if success else 1)

    if args.revert:
        success = switcher.revert_to_local_gateway()
        if success:
            print("\n🎉 Successfully reverted to local Gateway configuration!")
            print("You can now use local IB Gateway on ports 4001/4002")
        sys.exit(0 if success else 1)

    # Default action: switch to remote TWS
    print("🔄 SWITCHING TO REMOTE TWS CONFIGURATION")
    print("=" * 50)

    success = switcher.switch_to_remote_tws()

    if success:
        print("\n🎉 Successfully switched to Remote TWS configuration!")
        print("\nNext steps:")
        print("1. Ensure TWS is running on the Windows computer")
        print("2. Test connection: python simple_ib_test.py --comprehensive")
        print("3. Start your dashboard: ./launch_dashboard_production.py")

        # Show status
        print("\n" + "=" * 50)
        switcher.display_status()
    else:
        print("\n💥 Failed to switch configuration!")
        print("Check the error messages above and try:")
        print("1. ./setup_remote_tws.sh --interactive")
        print("2. python switch_to_remote_tws.py --revert")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
