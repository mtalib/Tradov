#!/usr/bin/env python3
"""
NUCLEAR JTS.INI FIXER - AUTOMATIC VERSION
Completely rebuilds jts.ini with minimal, guaranteed-to-work settings
Non-interactive version that automatically stops Gateway and applies fixes
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime

# Paths
JTS_PATH = Path.home() / "Jts"
JTS_INI = JTS_PATH / "jts.ini"
BACKUP_DIR = JTS_PATH / "backups"

# Create backup directory
BACKUP_DIR.mkdir(exist_ok=True)


def log_info(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ℹ️  {message}")


def log_success(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ✅ {message}")


def log_warning(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ⚠️  {message}")


def log_error(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ❌ {message}")


def backup_current_config():
    """Backup current jts.ini if it exists"""
    if JTS_INI.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"jts.ini.nuclear_backup_{timestamp}"
        shutil.copy2(JTS_INI, backup_file)
        log_success(f"Backed up current config to: {backup_file}")
        return backup_file
    return None


def create_nuclear_jts_ini():
    """
    Create a NUCLEAR minimal jts.ini with ONLY what's needed for API
    This is the absolute minimum configuration that should work
    """

    config = """[IBGateway]
# NUCLEAR MINIMAL API CONFIGURATION
TradingMode=paper
LocalServerPort=4002
SocketPort=4002
SocketPortSsl=4001

# TRUSTED IPS - LOCALHOST ONLY
TrustedIPs=127.0.0.1,::1

# API ENABLEMENT - CRITICAL
EnableApi=true
ApiOnly=false
ReadOnlyApi=false

# CONNECTION SETTINGS
AllowLocalhost=true
LocalhostOnly=true
MaxConnections=10
ConnectionTimeout=30

# LOGGING - COMPLETELY DISABLED
logApi=false
logAct=false
logSys=false
DisableApiLog=true
ApiLogLvl=1

# AUTHENTICATION
s3store=true
useRemoteSettings=false

[Logon]
tradingMode=p
Locale=en
UseSSL=true
TimeZone=Europe/Lisbon

[Communication]
Peer=cdc1.ibllc.com:4001
Region=us
"""

    return config


def verify_gateway_running():
    """Check if Gateway is running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    except:
        return False


def kill_gateway():
    """Kill Gateway process"""
    try:
        subprocess.run(["pkill", "-f", "ibgateway"], check=False)
        log_success("Stopped IB Gateway")
        return True
    except Exception as e:
        log_error(f"Failed to stop Gateway: {e}")
        return False


def start_gateway():
    """Start Gateway in background"""
    try:
        gateway_exe = Path.home() / "Jts" / "ibgateway" / "1039" / "ibgateway"
        if gateway_exe.exists():
            subprocess.Popen(
                [str(gateway_exe)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            log_success("Started IB Gateway")
            return True
        else:
            log_error(f"Gateway executable not found at: {gateway_exe}")
            return False
    except Exception as e:
        log_error(f"Failed to start Gateway: {e}")
        return False


def test_connection_after_restart():
    """Test connection after nuclear reset"""
    log_info("Waiting 20 seconds for Gateway to initialize...")
    time.sleep(20)

    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if result == 0:
            log_success("Socket connection test PASSED")
            return True
        else:
            log_warning(f"Socket connection failed: {result}")
            return False
    except Exception as e:
        log_warning(f"Connection test error: {e}")
        return False


def main():
    print("=" * 70)
    print("🔥 NUCLEAR JTS.INI CONFIGURATION RESET (AUTOMATIC)")
    print("=" * 70)
    print()

    # Step 1: Check Gateway status
    gateway_running = verify_gateway_running()
    if gateway_running:
        log_info("IB Gateway is running - will restart with new config")
    else:
        log_info("IB Gateway is not running")

    # Step 2: Stop Gateway if running
    if gateway_running:
        log_info("Stopping IB Gateway...")
        if not kill_gateway():
            log_error("Failed to stop Gateway - continuing anyway")
        else:
            log_info("Waiting 5 seconds for clean shutdown...")
            time.sleep(5)

    # Step 3: Backup current config
    log_info("Backing up current configuration...")
    backup_file = backup_current_config()

    # Step 4: Create nuclear config
    log_info("Creating nuclear minimal configuration...")
    nuclear_config = create_nuclear_jts_ini()

    # Step 5: Write new config
    log_info("Writing new jts.ini...")
    try:
        with open(JTS_INI, "w") as f:
            f.write(nuclear_config)
        log_success(f"Created new jts.ini at: {JTS_INI}")
    except Exception as e:
        log_error(f"Error writing jts.ini: {e}")
        return False

    # Step 6: Start Gateway with new config
    if gateway_running:
        log_info("Starting IB Gateway with nuclear configuration...")
        if start_gateway():
            # Step 7: Test the connection
            connection_ok = test_connection_after_restart()

            if connection_ok:
                log_success("Nuclear reset appears successful!")
            else:
                log_warning("Socket connection failed - may need GUI activation")
        else:
            log_error("Failed to restart Gateway")

    # Show what we created
    print("\n" + "=" * 70)
    print("📄 NEW NUCLEAR CONFIGURATION APPLIED:")
    print("=" * 70)
    print(nuclear_config)
    print("=" * 70)

    print("\n✅ NUCLEAR RESET COMPLETE!")
    print("\n📋 NEXT STEPS:")
    print("1. Wait for Gateway GUI to fully load (if started)")
    print("2. Login to your paper trading account")
    print("3. Go to Configure → Settings → API → Settings")
    print("4. ✅ Enable 'Enable ActiveX and Socket EClients'")
    print("5. ✅ Verify Socket port: 4002")
    print("6. ✅ Verify 'Allow connections from localhost only'")
    print("7. ✅ Add 127.0.0.1 to Trusted IP Addresses (if not there)")
    print("8. Click OK to activate API")
    print()
    print("🧪 TEST THE CONNECTION:")
    print('   python3 -c "')
    print("   from ib_insync import IB")
    print("   ib = IB()")
    print("   ib.connect('127.0.0.1', 4002, clientId=1)")
    print("   print('✅ Connected!', ib.managedAccounts())")
    print('   ib.disconnect()"')
    print()
    print("💡 If connection still fails after GUI activation:")
    print("   - Restart Gateway completely")
    print("   - Check for error messages in Gateway")
    print("   - Consider Gateway reinstall if persistent")
    print()

    return True


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
