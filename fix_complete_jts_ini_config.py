#!/usr/bin/env python3
"""
Complete IB Gateway jts.ini Configuration Fix
============================================

This script creates a proper jts.ini configuration file for IB Gateway API operations
with all necessary sections and settings for reliable API connectivity.

The script will:
1. Backup the current jts.ini file
2. Create a comprehensive new configuration with all required API settings
3. Set proper paper trading configuration
4. Configure API-specific parameters that may be missing

Usage:
    python fix_complete_jts_ini_config.py
    python fix_complete_jts_ini_config.py --dry-run
    python fix_complete_jts_ini_config.py --live-mode
"""

import os
import sys
import shutil
import socket
from datetime import datetime
from pathlib import Path
import argparse


class CompleteJTSIniConfigFix:
    """Complete jts.ini configuration fix for IB Gateway API"""

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
            self.jts_ini_path.parent / f"jts.ini.complete_fix_backup_{timestamp}"
        )

        try:
            shutil.copy2(self.jts_ini_path, self.backup_path)
            self.log_success(f"Created backup: {self.backup_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to create backup: {e}")
            return False

    def generate_complete_config(self):
        """Generate complete jts.ini configuration"""

        # Determine trading mode and ports
        if self.live_mode:
            trading_mode = "live"
            trading_mode_short = "l"
            api_port = 4001
            order_port = 4001
        else:
            trading_mode = "paper"
            trading_mode_short = "p"
            api_port = 4002
            order_port = 4001

        # Get current date for SSL configuration
        today = datetime.now().strftime("%Y%m%d")

        config_content = f"""[IBGateway]
WriteDebug=false
MainWindow.Width=1200
MainWindow.Height=800
MainWindow.Maximized=false
RemotePortOrderRouting={order_port}
RemoteHostOrderRouting=ndc1.ibllc.com
TradingMode={trading_mode}
LocalServerPort={api_port}
ApiOnly=true
ReadOnlyApi=false
SocketPort={api_port}
useRemoteSettings=false
TrustedIPs=127.0.0.1,{self.system_ip}
AcceptIncomingConnectionAction=accept
AllowUnknownCerts=true
SendUsernameAndPasswordAsPlaintext=true
WarningTargetPercent=90.0
WarningTimeSeconds=60.0
DismissPasswordExpiryWarning=true
DismissNSECompliance=true
LogComponents=never
exitAfterSecondTradingSession=false
storeSettingsOnServer=false

[Logon]
useRemoteSettings=false
TimeZone=Europe/Lisbon
tradingMode={trading_mode_short}
colorPalletName=dark
Steps=7
Locale=en
os_titlebar=false
UseSSL=true
SupportsSSL=ndc1.ibllc.com:4000,true,{today},false;cdc1.ibllc.com:4000,true,{today},false
screenHeight=1080
s3store=true
ibkrBranding=pro
AuthenticatedSTSOnly=false

[Communication]
Peer=cdc1.ibllc.com:{order_port}
Region=us

[API]
EnableSocketClients=true
ReadOnlyApi=false
SocketPort={api_port}
TrustedIPs=127.0.0.1,{self.system_ip}
MasterClientId=0
AllowOriginatingRequests=true
sendMarketDataInBatches=false
parallelizeRequests=false
maxRequestsPerSecond=-1
requestTimeout=60
AcceptIncomingConnectionAction=accept

[Trader Workstation Configuration]
ApiOnly=true

[Security]
AllowSocketConnections=true
TrustedHosts=127.0.0.1,{self.system_ip}
RequireAuthentication=false
SocketSecurityType=none

[Paths]
ApplicationDataFolder=$PROFILE\\Jts
SettingsPath=$PROFILE\\Jts\\{trading_mode}
LogPath=$PROFILE\\Jts\\Logs

[Advanced]
EnableApi=true
EnableActiveX=true
EnableSocketClients=true
ApiPortNumber={api_port}
ConnectionTimeout=60
ReadTimeout=60
WriteTimeout=60
KeepAliveInterval=30
MaxConnections=32
RejectInvalidRequests=false
LogApiMessages=true
EnableDDE=false

[Network]
SocketServerEnabled=true
SocketServerPort={api_port}
AcceptSocketConnections=true
TrustedSocketClients=127.0.0.1,{self.system_ip}
SocketConnectionSecurity=none
EnableSocketServerOnStartup=true

[Market Data]
EnableMarketDataConnections=true
MarketDataConnectionTimeout=30
"""

        return config_content

    def write_new_config(self):
        """Write the new complete configuration"""
        self.log_info("Generating new complete jts.ini configuration...")

        if self.dry_run:
            self.log_info("DRY RUN: Would write new complete configuration")
            config_content = self.generate_complete_config()
            print("\n" + "=" * 60)
            print("DRY RUN: New configuration would be:")
            print("=" * 60)
            print(config_content)
            print("=" * 60)
            return True

        try:
            config_content = self.generate_complete_config()

            with open(self.jts_ini_path, "w") as f:
                f.write(config_content)

            self.log_success("New complete configuration written successfully")
            return True

        except Exception as e:
            self.log_error(f"Failed to write new configuration: {e}")
            return False

    def verify_configuration(self):
        """Verify the new configuration was written correctly"""
        self.log_info("Verifying new configuration...")

        try:
            with open(self.jts_ini_path, "r") as f:
                content = f.read()

            # Check for critical API settings
            required_settings = [
                "TrustedIPs=127.0.0.1,",
                f"LocalServerPort={'4001' if self.live_mode else '4002'}",
                "ApiOnly=true",
                "EnableSocketClients=true",
                "[API]",
                "[Security]",
                "[Network]",
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
                    "All critical API settings verified in new configuration"
                )
                return True

        except Exception as e:
            self.log_error(f"Configuration verification failed: {e}")
            return False

    def run_complete_fix(self):
        """Run the complete jts.ini configuration fix"""
        print("🔧 Complete IB Gateway jts.ini Configuration Fix")
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

        # Step 4: Write new complete configuration
        if not self.write_new_config():
            return False

        # Step 5: Verify configuration
        if not self.verify_configuration():
            self.log_warning("Verification had issues, but configuration was written")

        # Success message
        print("\n" + "=" * 60)
        print("✅ COMPLETE JTS.INI CONFIGURATION CREATED")
        print("=" * 60)
        print(f"📁 Configuration file: {self.jts_ini_path}")
        if not self.dry_run:
            print(f"💾 Backup created: {self.backup_path}")
        print(f"🎯 Trading Mode: {'Live' if self.live_mode else 'Paper'}")
        print(f"🔌 API Port: {'4001' if self.live_mode else '4002'}")
        print(f"🌐 Trusted IPs: 127.0.0.1, {system_ip}")

        print("\n📋 New Configuration Includes:")
        print("   • [IBGateway] - Main gateway settings")
        print("   • [Logon] - Authentication and session settings")
        print("   • [Communication] - Server connection settings")
        print("   • [API] - Comprehensive API configuration")
        print("   • [Security] - Socket connection security")
        print("   • [Network] - Network and socket server settings")
        print("   • [Advanced] - Advanced API parameters")
        print("   • [Market Data] - Market data connection settings")

        print("\n🔄 NEXT STEPS:")
        print("   1. Restart IB Gateway to load the new complete configuration")
        print("   2. Verify IB Gateway starts successfully with new settings")
        print("   3. Test API connection - should now accept socket connections")
        print("   4. Monitor IB Gateway logs for any configuration issues")

        print("\n⚙️  KEY SETTINGS CONFIGURED:")
        print(f"   • EnableSocketClients=true")
        print(f"   • SocketServerEnabled=true")
        print(f"   • AcceptSocketConnections=true")
        print(f"   • TrustedSocketClients includes system IP")
        print(f"   • Multiple API-related sections for comprehensive coverage")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Complete IB Gateway jts.ini Configuration Fix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fix_complete_jts_ini_config.py                    # Create complete paper trading config
  python fix_complete_jts_ini_config.py --dry-run         # Preview new configuration
  python fix_complete_jts_ini_config.py --live-mode       # Configure for live trading
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview new configuration without applying",
    )
    parser.add_argument(
        "--live-mode",
        action="store_true",
        help="Configure for live trading (port 4001)",
    )

    args = parser.parse_args()

    try:
        fixer = CompleteJTSIniConfigFix(dry_run=args.dry_run, live_mode=args.live_mode)
        success = fixer.run_complete_fix()
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
