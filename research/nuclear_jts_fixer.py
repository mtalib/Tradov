#!/usr/bin/env python3
"""
NUCLEAR JTS.INI FIXER - Complete Configuration Reset
Completely rebuilds jts.ini with minimal, guaranteed-to-work settings
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Paths
JTS_PATH = Path.home() / "Jts"
JTS_INI = JTS_PATH / "jts.ini"
BACKUP_DIR = JTS_PATH / "backups"

# Create backup directory
BACKUP_DIR.mkdir(exist_ok=True)

def backup_current_config():
    """Backup current jts.ini if it exists"""
    if JTS_INI.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"jts.ini.backup_{timestamp}"
        shutil.copy2(JTS_INI, backup_file)
        print(f"✅ Backed up current config to: {backup_file}")
        return backup_file
    return None

def create_nuclear_jts_ini():
    """
    Create a NUCLEAR minimal jts.ini with ONLY what's needed for API
    This is the absolute minimum configuration that should work
    """
    
    config = """[IBGateway]
# CRITICAL API SETTINGS - DO NOT MODIFY
TradingMode=paper
LocalServerPort=4002
ApiOnly=false
ReadOnlyApi=false

# TRUSTED IPS - CRITICAL FOR LOCALHOST
TrustedIPs=127.0.0.1,::1

# LOGGING - DISABLED FOR STABILITY
logApi=false
logComponents=never
logLevel=warning

# CONNECTION SETTINGS
AllowLocalhost=true
LocalhostOnly=true
MaxConnections=10

# AUTHENTICATION
s3store=true
useRemoteSettings=false

[Logon]
tradingMode=p
Locale=en
colorPaletteName=dark
UseSSL=true
Steps2FAMobileDevice=OPT OUT
Steps2FAEmailDevice=OPT OUT
Steps2FASecurityCodeDevice=OPT OUT
"""
    
    return config

def verify_gateway_running():
    """Check if Gateway is running"""
    import subprocess
    try:
        result = subprocess.run(['pgrep', '-f', 'ibgateway'], 
                              capture_output=True, text=True)
        return bool(result.stdout.strip())
    except:
        return False

def kill_gateway():
    """Kill Gateway process"""
    import subprocess
    try:
        subprocess.run(['pkill', '-f', 'ibgateway'], check=False)
        print("✅ Stopped IB Gateway")
        return True
    except:
        return False

def main():
    print("=" * 70)
    print("🔥 NUCLEAR JTS.INI CONFIGURATION RESET")
    print("=" * 70)
    print()
    
    # Check if Gateway is running
    if verify_gateway_running():
        print("⚠️  IB Gateway is currently running")
        response = input("   Stop Gateway to apply changes? (y/n): ")
        if response.lower() == 'y':
            kill_gateway()
            print("   Waiting 5 seconds...")
            import time
            time.sleep(5)
        else:
            print("❌ Cannot modify jts.ini while Gateway is running")
            return False
    
    # Backup current config
    print("\n📦 STEP 1: Backing up current configuration...")
    backup_file = backup_current_config()
    
    # Create nuclear config
    print("\n🔥 STEP 2: Creating nuclear minimal configuration...")
    nuclear_config = create_nuclear_jts_ini()
    
    # Write new config
    print("\n💾 STEP 3: Writing new jts.ini...")
    try:
        with open(JTS_INI, 'w') as f:
            f.write(nuclear_config)
        print(f"✅ Created new jts.ini at: {JTS_INI}")
    except Exception as e:
        print(f"❌ Error writing jts.ini: {e}")
        return False
    
    # Show what we created
    print("\n📄 NEW CONFIGURATION:")
    print("-" * 70)
    print(nuclear_config)
    print("-" * 70)
    
    print("\n✅ NUCLEAR RESET COMPLETE!")
    print("\n📋 NEXT STEPS:")
    print("1. Start IB Gateway manually")
    print("2. Let it fully load (wait for login window)")
    print("3. Login to your paper trading account")
    print("4. Wait for Gateway to be fully ready")
    print("5. Run this test:")
    print()
    print("   python3 -c \"")
    print("   from ib_insync import IB")
    print("   ib = IB()")
    print("   ib.connect('127.0.0.1', 4002, clientId=1)")
    print("   print('✅ Connected!', ib.managedAccounts())")
    print("   ib.disconnect()")
    print("   \"")
    print()
    print("💡 If this still doesn't work, the issue is:")
    print("   - Gateway GUI API settings (check Configure > Settings > API)")
    print("   - Firewall blocking localhost")
    print("   - Gateway installation corruption")
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
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
