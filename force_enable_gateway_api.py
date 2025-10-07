#!/usr/bin/env python3
"""
Force Enable IB Gateway API Configuration
==========================================

This script forces the IB Gateway API to be properly enabled by:
1. Stopping the current Gateway process
2. Creating a minimal, correct configuration
3. Starting Gateway with API enabled
4. Testing the connection

The script handles the common issue where Gateway API is configured
but not actually listening on ports due to GUI settings conflicts.

Usage:
    python force_enable_gateway_api.py
    python force_enable_gateway_api.py --dry-run
"""

import os
import sys
import time
import signal
import socket
import subprocess
from datetime import datetime
from pathlib import Path
import argparse


class ForceEnableGatewayAPI:
    """Force enable IB Gateway API with proper configuration"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.jts_ini_path = Path.home() / "Jts" / "jts.ini"
        self.config_dir = None
        self.gateway_exe = None

    def log_info(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ℹ️  {message}")

    def log_success(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ✅ {message}")

    def log_warning(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ⚠️  {message}")

    def log_error(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ❌ {message}")

    def find_gateway_executable(self) -> bool:
        """Find IB Gateway executable"""
        self.log_info("Locating IB Gateway executable...")

        possible_paths = [
            Path.home() / "Jts" / "ibgateway" / "1039" / "ibgateway",
            Path.home() / "Jts" / "ibgateway" / "latest" / "ibgateway",
            Path("/opt/ibgateway/ibgateway"),
            Path("/usr/local/ibgateway/ibgateway"),
        ]

        for path in possible_paths:
            if path.exists() and path.is_file():
                self.gateway_exe = path
                self.log_success(f"Found Gateway executable: {path}")
                return True

        self.log_error("Could not find IB Gateway executable")
        return False

    def stop_all_gateway_processes(self) -> bool:
        """Stop all running IB Gateway processes"""
        self.log_info("Stopping all IB Gateway processes...")

        if self.dry_run:
            self.log_info("DRY RUN: Would stop Gateway processes")
            return True

        try:
            # Find all Gateway processes
            result = subprocess.run(
                ["pgrep", "-f", "ibgateway"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = [int(pid) for pid in result.stdout.strip().split("\n")]

                for pid in pids:
                    try:
                        self.log_info(f"Stopping Gateway process {pid}...")
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass  # Process already gone

                # Wait for graceful shutdown
                time.sleep(5)

                # Force kill any remaining processes
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

                self.log_success("All Gateway processes stopped")
            else:
                self.log_info("No Gateway processes found to stop")

            return True

        except Exception as e:
            self.log_error(f"Failed to stop Gateway processes: {e}")
            return False

    def backup_current_config(self) -> bool:
        """Backup current configuration"""
        if not self.jts_ini_path.exists():
            self.log_info("No existing jts.ini to backup")
            return True

        if self.dry_run:
            self.log_info("DRY RUN: Would backup current configuration")
            return True

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.jts_ini_path.parent / f"jts.ini.backup_force_{timestamp}"

            import shutil

            shutil.copy2(self.jts_ini_path, backup_path)

            self.log_success(f"Backed up configuration to: {backup_path}")
            return True

        except Exception as e:
            self.log_error(f"Failed to backup configuration: {e}")
            return False

    def create_minimal_api_config(self) -> bool:
        """Create minimal working API configuration"""
        self.log_info("Creating minimal API-enabled configuration...")

        if self.dry_run:
            self.log_info("DRY RUN: Would create minimal API configuration")
            return True

        # Get system IP
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
        except:
            local_ip = "192.168.1.9"

        # Minimal working configuration
        config_content = f"""[IBGateway]
TradingMode=paper
LocalServerPort=4002
SocketPort=4002
SocketPortSsl=4001
TrustedIPs=127.0.0.1,{local_ip},0.0.0.0
EnableApi=true
ApiOnly=false
AllowLocalhost=true
LocalhostOnly=true
logApi=false
logAct=false
logSys=false
DisableApiLog=true
ApiLogLvl=1
ReadOnlyApi=false
MaxConnections=50
ConnectionTimeout=30
MaintenanceTime=23:45

[Logon]
useRemoteSettings=false
tradingMode=p
TimeZone=Europe/Lisbon
Locale=en
UseSSL=true
Steps=6

[Communication]
Peer=cdc1.ibllc.com:4001
Region=us
"""

        try:
            # Ensure directory exists
            self.jts_ini_path.parent.mkdir(parents=True, exist_ok=True)

            # Write configuration
            with open(self.jts_ini_path, "w") as f:
                f.write(config_content)

            self.log_success("Created minimal API configuration")
            return True

        except Exception as e:
            self.log_error(f"Failed to create configuration: {e}")
            return False

    def clean_config_directory(self) -> bool:
        """Clean corrupted configuration files"""
        self.log_info("Cleaning corrupted configuration files...")

        config_dirs = [
            Path.home() / "Jts" / "goeocikbdlcolmakgpjebcbggggkdadfahoblcfk",
            Path.home() / "Jts" / "settings",
        ]

        if self.dry_run:
            self.log_info("DRY RUN: Would clean configuration directories")
            return True

        cleaned_any = False
        for config_dir in config_dirs:
            if config_dir.exists():
                try:
                    # Remove corrupted XML files
                    xml_files = list(config_dir.glob("*.xml"))
                    for xml_file in xml_files:
                        try:
                            # Check if file is corrupted by trying to read first line
                            with open(xml_file, "r") as f:
                                first_line = f.readline()
                                if len(first_line) < 10 or "xml" not in first_line:
                                    xml_file.unlink()
                                    self.log_info(f"Removed corrupted: {xml_file.name}")
                                    cleaned_any = True
                        except:
                            # If we can't read it, it's probably corrupted
                            try:
                                xml_file.unlink()
                                self.log_info(f"Removed unreadable: {xml_file.name}")
                                cleaned_any = True
                            except:
                                pass

                except Exception as e:
                    self.log_warning(f"Error cleaning {config_dir}: {e}")

        if cleaned_any:
            self.log_success("Cleaned corrupted configuration files")
        else:
            self.log_info("No corrupted files found to clean")

        return True

    def start_gateway_with_api(self) -> bool:
        """Start IB Gateway with API enabled"""
        self.log_info("Starting IB Gateway with API enabled...")

        if self.dry_run:
            self.log_info("DRY RUN: Would start IB Gateway")
            return True

        if not self.gateway_exe:
            self.log_error("Gateway executable not found")
            return False

        try:
            # Start Gateway
            self.log_info(f"Executing: {self.gateway_exe}")

            process = subprocess.Popen(
                [str(self.gateway_exe)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(self.gateway_exe.parent),
            )

            # Wait for startup
            self.log_info("Waiting for Gateway to initialize (20 seconds)...")
            time.sleep(20)

            # Check if process is running
            if process.poll() is None:
                self.log_success("IB Gateway started successfully")
                return True
            else:
                self.log_error("Gateway process exited unexpectedly")
                return False

        except Exception as e:
            self.log_error(f"Failed to start Gateway: {e}")
            return False

    def test_api_connection(self) -> bool:
        """Test API connection to verify it's working"""
        self.log_info("Testing API connection...")

        if self.dry_run:
            self.log_info("DRY RUN: Would test API connection")
            return True

        # Test socket connection
        for port in [4002, 4001]:  # Paper, then Live
            try:
                self.log_info(f"Testing port {port}...")

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    result = s.connect_ex(("127.0.0.1", port))

                    if result == 0:
                        self.log_success(f"✅ Port {port} is accessible")

                        # Try basic API handshake
                        try:
                            # Send minimal API version message
                            s.send(b"\x00\x00\x00\x0f100\x00\x00\x00\x01999\x00")
                            s.settimeout(3)
                            response = s.recv(1024)

                            if response:
                                self.log_success(
                                    f"✅ Port {port} API responds to handshake"
                                )
                                return True
                            else:
                                self.log_info(
                                    f"Port {port} connected but no API response"
                                )

                        except Exception as e:
                            self.log_info(
                                f"Port {port} connected but handshake failed: {e}"
                            )

                    else:
                        self.log_warning(f"❌ Port {port} connection failed: {result}")

            except Exception as e:
                self.log_warning(f"❌ Port {port} test failed: {e}")

        self.log_error("No API ports are responding properly")
        return False

    def wait_for_gui_setup(self) -> bool:
        """Wait and provide instructions for GUI setup"""
        if self.dry_run:
            return True

        print("\n" + "=" * 60)
        print("🖥️  MANUAL GUI CONFIGURATION REQUIRED")
        print("=" * 60)
        print("IB Gateway should now be starting. Please:")
        print("1. ⏳ Wait for the Gateway window to appear")
        print("2. 🔑 Log in with your IBKR credentials")
        print("3. ⚙️  Navigate to: Configure → Settings → API → Settings")
        print("4. ✅ Check 'Enable ActiveX and Socket EClients'")
        print("5. 🔌 Set Socket port to: 4002")
        print("6. 🏠 Check 'Allow connections from localhost only'")
        print("7. 🛡️  Add to Trusted IP Addresses: 127.0.0.1")
        print("8. 💾 Click 'OK' to save settings")
        print("9. ✨ The API should now be active!")
        print("=" * 60)

        input("\n⏸️  Press Enter when you have completed the above steps...")

        # Give a moment for settings to take effect
        self.log_info("Waiting 10 seconds for settings to apply...")
        time.sleep(10)

        return True

    def run_force_enable(self) -> bool:
        """Run the complete force enable process"""
        print("🚀 FORCE ENABLE IB GATEWAY API")
        print("=" * 50)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

        # Step 1: Find Gateway executable
        if not self.find_gateway_executable():
            return False

        # Step 2: Stop all Gateway processes
        if not self.stop_all_gateway_processes():
            self.log_warning("Could not stop all processes, continuing...")

        # Step 3: Backup current configuration
        if not self.backup_current_config():
            self.log_warning("Could not backup config, continuing...")

        # Step 4: Clean corrupted configuration
        if not self.clean_config_directory():
            self.log_warning("Could not clean config directory, continuing...")

        # Step 5: Create minimal API configuration
        if not self.create_minimal_api_config():
            return False

        # Step 6: Start Gateway
        if not self.start_gateway_with_api():
            return False

        # Step 7: Wait for manual GUI configuration
        if not self.wait_for_gui_setup():
            return False

        # Step 8: Test API connection
        if not self.test_api_connection():
            self.log_error("API connection test failed")
            print("\n💡 TROUBLESHOOTING:")
            print("   - Verify Gateway is logged in")
            print("   - Check API settings in Gateway GUI")
            print("   - Ensure no firewall is blocking ports")
            print("   - Try restarting Gateway after configuration")
            return False

        # Success!
        print("\n" + "=" * 50)
        print("✅ IB GATEWAY API FORCE ENABLED SUCCESSFULLY!")
        print("=" * 50)
        print("🎉 The API is now active and responding")
        print("🔗 You can now connect your trading applications")
        print("📍 Connection details:")
        print("   Host: 127.0.0.1")
        print("   Port: 4002 (Paper Trading)")
        print("   Port: 4001 (Live Trading)")
        print("\n🚀 NEXT STEPS:")
        print("   1. Test with your SPYDER dashboard")
        print("   2. Run: python test_simple_gateway_connection.py")
        print("   3. Launch: python launch_spyder_dashboard_direct.py")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Force Enable IB Gateway API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script forces IB Gateway API to be properly enabled by:
- Stopping current Gateway processes
- Creating clean, minimal configuration
- Starting Gateway with API settings
- Guiding through GUI configuration
- Testing the connection

Examples:
  python force_enable_gateway_api.py           # Full force enable
  python force_enable_gateway_api.py --dry-run # Preview only
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview actions without executing them"
    )

    args = parser.parse_args()

    try:
        enabler = ForceEnableGatewayAPI(dry_run=args.dry_run)
        success = enabler.run_force_enable()
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
