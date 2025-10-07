#!/usr/bin/env python3
"""
SPYDER - IB Gateway API Configuration Fix and Restart

This script ensures IB Gateway is properly configured for API access
and restarts it cleanly to activate the settings.
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path
import configparser
import shutil
from datetime import datetime


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'=' * 60}")
    print(f"🕷️  {title}")
    print(f"{'=' * 60}")


def print_step(step_num, description):
    """Print a formatted step"""
    print(f"\n[Step {step_num}] {description}")


def check_gateway_process():
    """Check if IB Gateway is currently running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            return [pid for pid in pids if pid]
        return []
    except Exception as e:
        print(f"⚠️  Error checking Gateway process: {e}")
        return []


def kill_gateway_processes():
    """Safely terminate IB Gateway processes"""
    pids = check_gateway_process()

    if not pids:
        print("✅ No IB Gateway processes running")
        return True

    print(f"🔄 Found {len(pids)} IB Gateway process(es): {', '.join(pids)}")

    # Try graceful shutdown first
    for pid in pids:
        try:
            print(f"   Sending SIGTERM to process {pid}...")
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            print(f"   Process {pid} already terminated")
        except Exception as e:
            print(f"   Error terminating {pid}: {e}")

    # Wait for graceful shutdown
    print("⏳ Waiting 5 seconds for graceful shutdown...")
    time.sleep(5)

    # Check if any processes remain
    remaining_pids = check_gateway_process()

    if remaining_pids:
        print(f"🔨 Force killing remaining processes: {', '.join(remaining_pids)}")
        for pid in remaining_pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except Exception as e:
                print(f"   Error force killing {pid}: {e}")

        time.sleep(2)
        final_pids = check_gateway_process()
        if final_pids:
            print(f"❌ Failed to terminate processes: {', '.join(final_pids)}")
            return False

    print("✅ All IB Gateway processes terminated")
    return True


def backup_jts_ini():
    """Backup the current jts.ini file"""
    jts_path = Path("/home/adam/Jts/jts.ini")

    if not jts_path.exists():
        print(f"⚠️  jts.ini not found at {jts_path}")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = jts_path.parent / f"jts_backup_{timestamp}.ini"

    try:
        shutil.copy2(jts_path, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None


def fix_jts_ini():
    """Fix the jts.ini configuration for proper API access"""
    jts_path = Path("/home/adam/Jts/jts.ini")

    if not jts_path.exists():
        print(f"❌ jts.ini not found at {jts_path}")
        return False

    try:
        # Read current configuration
        config = configparser.ConfigParser()

        # Read with case-sensitive keys
        config.optionxform = str
        config.read(jts_path)

        print("📄 Current IB Gateway configuration:")

        # Ensure [IBGateway] section exists
        if "IBGateway" not in config:
            config.add_section("IBGateway")
            print("   + Added [IBGateway] section")

        # Critical API settings
        api_settings = {
            "ApiOnly": "true",
            "ReadOnlyApi": "false",
            "LocalServerPort": "4002",
            "SocketPort": "4002",
            "TradingMode": "paper",
            "TrustedIPs": "127.0.0.1,192.168.1.0/24,0.0.0.0",
            "allowOrigSub": "1",
            "masterClientID": "0",
        }

        changes_made = []

        for key, value in api_settings.items():
            current_value = config.get("IBGateway", key, fallback=None)
            if current_value != value:
                config.set("IBGateway", key, value)
                changes_made.append(f"{key}: {current_value} → {value}")
                print(f"   ✏️  {key}: {current_value} → {value}")
            else:
                print(f"   ✅ {key}: {value} (unchanged)")

        # Ensure [Logon] section has correct settings
        if "Logon" not in config:
            config.add_section("Logon")
            print("   + Added [Logon] section")

        logon_settings = {
            "tradingMode": "p",  # p = paper, l = live
        }

        for key, value in logon_settings.items():
            current_value = config.get("Logon", key, fallback=None)
            if current_value != value:
                config.set("Logon", key, value)
                changes_made.append(f"Logon.{key}: {current_value} → {value}")
                print(f"   ✏️  Logon.{key}: {current_value} → {value}")

        if changes_made:
            # Write updated configuration
            with open(jts_path, "w") as f:
                config.write(f, space_around_delimiters=False)

            print(f"\n✅ Configuration updated with {len(changes_made)} changes:")
            for change in changes_made:
                print(f"      {change}")
        else:
            print("\n✅ Configuration already correct - no changes needed")

        return True

    except Exception as e:
        print(f"❌ Failed to fix jts.ini: {e}")
        return False


def start_gateway():
    """Start IB Gateway"""
    gateway_path = Path("/home/adam/Jts/ibgateway/1039/ibgateway")

    if not gateway_path.exists():
        print(f"❌ IB Gateway executable not found at {gateway_path}")
        return False

    try:
        print("🚀 Starting IB Gateway...")

        # Start Gateway in background
        process = subprocess.Popen(
            [str(gateway_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,  # Create new process group
        )

        print(f"   Process started with PID: {process.pid}")

        # Wait a moment for startup
        print("⏳ Waiting for Gateway to initialize...")
        time.sleep(10)

        # Check if process is still running
        if process.poll() is None:
            print("✅ IB Gateway started successfully")
            return True
        else:
            print("❌ IB Gateway process terminated unexpectedly")
            return False

    except Exception as e:
        print(f"❌ Failed to start IB Gateway: {e}")
        return False


def test_api_connection():
    """Test if API connection works"""
    import socket

    print("🔍 Testing API connection...")

    # Wait for Gateway to fully initialize
    for attempt in range(30):  # 30 second timeout
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", 4002))
            sock.close()

            if result == 0:
                print("✅ API port (4002) is accessible")

                # Try actual API connection
                try:
                    from ibapi.client import EClient
                    from ibapi.wrapper import EWrapper
                    import threading

                    class TestWrapper(EWrapper):
                        def __init__(self):
                            super().__init__()
                            self.connected = False

                        def connectAck(self):
                            self.connected = True

                    wrapper = TestWrapper()
                    client = EClient(wrapper)

                    print("🔌 Testing API connection...")
                    client.connect("127.0.0.1", 4002, 999)

                    # Start message processing
                    api_thread = threading.Thread(target=client.run, daemon=True)
                    api_thread.start()

                    # Wait for connection
                    timeout_time = time.time() + 10
                    while time.time() < timeout_time:
                        if wrapper.connected:
                            print("✅ API connection successful!")
                            client.disconnect()
                            return True
                        time.sleep(0.1)

                    print("⚠️  API connection timeout")
                    client.disconnect()
                    return False

                except ImportError:
                    print("✅ Port accessible (IB API not installed for full test)")
                    return True
                except Exception as e:
                    print(f"⚠️  API test error: {e}")
                    return False
            else:
                print(f"   Attempt {attempt + 1}/30: Port not ready yet...")
                time.sleep(1)

        except Exception as e:
            print(f"   Connection test error: {e}")
            time.sleep(1)

    print("❌ API port not accessible after 30 seconds")
    return False


def main():
    """Main fix and restart sequence"""

    print_header("IB Gateway API Configuration Fix & Restart")
    print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")

    # Step 1: Backup current configuration
    print_step(1, "Backing up current configuration")
    backup_path = backup_jts_ini()

    # Step 2: Stop running Gateway
    print_step(2, "Stopping IB Gateway")
    if not kill_gateway_processes():
        print("❌ Failed to stop IB Gateway - please stop manually")
        return 1

    # Step 3: Fix configuration
    print_step(3, "Fixing jts.ini configuration")
    if not fix_jts_ini():
        print("❌ Failed to fix configuration")
        return 1

    # Step 4: Start Gateway
    print_step(4, "Starting IB Gateway")
    if not start_gateway():
        print("❌ Failed to start IB Gateway")
        return 1

    # Step 5: Test API connection
    print_step(5, "Testing API connection")
    if test_api_connection():
        print("\n🎉 SUCCESS!")
        print("✅ IB Gateway is running with API enabled")
        print("✅ Clients should now be visible in Gateway")
        print("\n💡 Next steps:")
        print("   1. Check IB Gateway interface for 'API' status")
        print("   2. Run your SPYDER trading system")
        print("   3. Verify clients appear in Gateway's client list")
        return 0
    else:
        print("\n❌ API CONNECTION FAILED")
        print("💡 Manual steps required:")
        print("   1. Open IB Gateway interface")
        print("   2. Go to Configure → Settings → API → Settings")
        print("   3. Check 'Enable ActiveX and Socket Clients'")
        print("   4. Set Socket port to 4002")
        print("   5. Add 127.0.0.1 to Trusted IPs")
        print("   6. Click OK and restart Gateway")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n⏰ Completed at: {datetime.now().strftime('%H:%M:%S')}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
