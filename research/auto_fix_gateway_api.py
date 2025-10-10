#!/usr/bin/env python3
"""
IB Gateway API Configuration Auto-Fixer
Automatically fixes all configuration issues preventing API connections

This script will:
1. Backup existing configurations
2. Create/fix jts.ini with proper API settings
3. Update IBC config.ini with AcceptIncomingConnectionAction
4. Verify the configuration
5. Provide next steps

Author: SPYDER Trading System
Date: 2025-10-09
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
import subprocess
import socket

# Configuration templates
JTS_INI_TEMPLATE = """[IBGateway]
WriteDebug=false
TrustedIPs=127.0.0.1
ApiOnly=true
MainWindow.Height=600
MainWindow.Width=800
RemoteHostOrderRouting=gdc1.ibllc.com
RemotePortOrderRouting=4000
LocalServerPort=4000

[Logon]
Locale=en
TimeZone=America/New_York
tradingMode=p
Individual=1
Steps=5
useRemoteSettings=false
colorPalletName=dark
UseSSL=true
s3store=true
displayedproxymsg=1

[Communication]
Internal=false
LocalPort=0
Peer=gdc1.ibllc.com:4001
Region=us
"""

IBC_API_SETTINGS = """
# ===============================================================================
# API CONFIGURATION - CRITICAL FOR CONNECTIONS
# ===============================================================================
AcceptIncomingConnectionAction=accept
AllowBlindTrading=yes
ReadOnlyLogin=no
ReadOnlyApi=no
AcceptNonBrokerageAccountWarning=yes
OverrideTwsApiPort=4002

# Session Handling
ExistingSessionDetectedAction=primary
StoreSettingsOnServer=yes
MinimizeMainWindow=yes
ConfirmExitApplication=no
IbAutoCloseDown=no
"""


class GatewayAPIFixer:
    """Automatically fix IB Gateway API configuration issues"""
    
    def __init__(self):
        self.home = Path.home()
        self.jts_dir = self.home / "Jts"
        self.ibc_dir = self.home / "ibc"
        self.backup_dir = self.home / "gateway_config_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.issues_found = []
        self.fixes_applied = []
        
    def print_header(self):
        """Print script header"""
        print("=" * 70)
        print("🔧 IB GATEWAY API CONFIGURATION AUTO-FIXER")
        print("=" * 70)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"User: {os.getenv('USER', 'unknown')}")
        print()
    
    def create_backup(self, file_path: Path) -> bool:
        """Create backup of a file"""
        if not file_path.exists():
            return False
            
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_dir / file_path.name
            shutil.copy2(file_path, backup_path)
            print(f"✅ Backed up {file_path.name} to {backup_path}")
            return True
        except Exception as e:
            print(f"⚠️  Could not backup {file_path.name}: {e}")
            return False
    
    def fix_jts_ini(self) -> bool:
        """Fix or create jts.ini file"""
        print("\n" + "=" * 70)
        print("1. FIXING jts.ini")
        print("=" * 70)
        
        jts_ini = self.jts_dir / "jts.ini"
        
        # Check if exists
        if jts_ini.exists():
            print(f"📋 Found existing jts.ini at {jts_ini}")
            self.create_backup(jts_ini)
            
            # Check for critical settings
            content = jts_ini.read_text()
            
            if "TrustedIPs=127.0.0.1" not in content:
                self.issues_found.append("jts.ini missing TrustedIPs=127.0.0.1")
                
            if "ApiOnly=true" not in content:
                self.issues_found.append("jts.ini missing ApiOnly=true")
        else:
            print(f"❌ jts.ini NOT FOUND at {jts_ini}")
            self.issues_found.append("jts.ini file missing")
        
        # Create new jts.ini
        try:
            self.jts_dir.mkdir(parents=True, exist_ok=True)
            jts_ini.write_text(JTS_INI_TEMPLATE)
            print(f"✅ Created new jts.ini with proper API configuration")
            self.fixes_applied.append("Created/updated jts.ini with API settings")
            
            # Verify critical settings
            content = jts_ini.read_text()
            if "TrustedIPs=127.0.0.1" in content:
                print("   ✅ TrustedIPs=127.0.0.1 configured")
            if "ApiOnly=true" in content:
                print("   ✅ ApiOnly=true configured")
            if "tradingMode=p" in content:
                print("   ✅ Paper trading mode set")
                
            return True
            
        except Exception as e:
            print(f"❌ Error creating jts.ini: {e}")
            return False
    
    def fix_ibc_config(self) -> bool:
        """Fix IBC config.ini file"""
        print("\n" + "=" * 70)
        print("2. FIXING IBC config.ini")
        print("=" * 70)
        
        config_ini = self.ibc_dir / "config.ini"
        
        if not config_ini.exists():
            print(f"⚠️  IBC config.ini not found at {config_ini}")
            print("   IBC may not be installed or configured yet")
            return False
        
        print(f"📋 Found IBC config at {config_ini}")
        self.create_backup(config_ini)
        
        # Read existing config
        content = config_ini.read_text()
        
        # Check for critical settings
        critical_settings = [
            "AcceptIncomingConnectionAction=accept",
            "OverrideTwsApiPort=4002"
        ]
        
        missing_settings = []
        for setting in critical_settings:
            if setting not in content:
                missing_settings.append(setting)
                self.issues_found.append(f"IBC config missing: {setting}")
        
        if missing_settings:
            print(f"❌ Missing critical API settings:")
            for setting in missing_settings:
                print(f"   - {setting}")
            
            # Add missing settings
            try:
                # Find a good place to insert (after credentials section)
                if "[API]" not in content:
                    content += "\n" + IBC_API_SETTINGS
                else:
                    # Replace existing API section
                    import re
                    content = re.sub(
                        r'\[API\].*?(?=\[|$)', 
                        IBC_API_SETTINGS, 
                        content, 
                        flags=re.DOTALL
                    )
                
                config_ini.write_text(content)
                print("✅ Added API configuration to IBC config.ini")
                self.fixes_applied.append("Updated IBC config.ini with API settings")
                return True
                
            except Exception as e:
                print(f"❌ Error updating IBC config: {e}")
                return False
        else:
            print("✅ IBC config already has correct API settings")
            return True
    
    def check_gateway_running(self) -> bool:
        """Check if Gateway is currently running"""
        print("\n" + "=" * 70)
        print("3. CHECKING GATEWAY STATUS")
        print("=" * 70)
        
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ibgateway"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                print(f"✅ Gateway is running (PIDs: {', '.join(pids)})")
                print("⚠️  You need to RESTART Gateway for changes to take effect")
                return True
            else:
                print("❌ Gateway is NOT running")
                return False
                
        except Exception as e:
            print(f"⚠️  Could not check Gateway status: {e}")
            return False
    
    def check_port_listening(self) -> bool:
        """Check if port 4002 is listening"""
        print("\n" + "=" * 70)
        print("4. CHECKING PORT STATUS")
        print("=" * 70)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', 4002))
            sock.close()
            
            if result == 0:
                print("✅ Port 4002 is OPEN and listening")
                return True
            else:
                print("❌ Port 4002 is NOT listening")
                print("   Gateway may need to be started")
                return False
                
        except Exception as e:
            print(f"⚠️  Could not check port: {e}")
            return False
    
    def verify_configuration(self) -> bool:
        """Verify all configurations are correct"""
        print("\n" + "=" * 70)
        print("5. VERIFICATION")
        print("=" * 70)
        
        all_ok = True
        
        # Check jts.ini
        jts_ini = self.jts_dir / "jts.ini"
        if jts_ini.exists():
            content = jts_ini.read_text()
            
            checks = [
                ("TrustedIPs=127.0.0.1", "TrustedIPs configured"),
                ("ApiOnly=true", "API mode enabled"),
                ("tradingMode=p", "Paper trading mode")
            ]
            
            for check_str, description in checks:
                if check_str in content:
                    print(f"✅ {description}")
                else:
                    print(f"❌ {description} - MISSING")
                    all_ok = False
        else:
            print("❌ jts.ini not found")
            all_ok = False
        
        # Check IBC config
        config_ini = self.ibc_dir / "config.ini"
        if config_ini.exists():
            content = config_ini.read_text()
            
            if "AcceptIncomingConnectionAction=accept" in content:
                print("✅ IBC configured to accept API connections")
            else:
                print("❌ IBC NOT configured to accept API connections")
                all_ok = False
        
        return all_ok
    
    def print_summary(self):
        """Print summary of actions taken"""
        print("\n" + "=" * 70)
        print("📊 SUMMARY")
        print("=" * 70)
        
        if self.issues_found:
            print("\n🔍 Issues Found:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"   {i}. {issue}")
        
        if self.fixes_applied:
            print("\n✅ Fixes Applied:")
            for i, fix in enumerate(self.fixes_applied, 1):
                print(f"   {i}. {fix}")
        
        if self.backup_dir.exists():
            print(f"\n💾 Backups saved to: {self.backup_dir}")
    
    def print_next_steps(self, gateway_running: bool):
        """Print next steps for user"""
        print("\n" + "=" * 70)
        print("🚀 NEXT STEPS")
        print("=" * 70)
        
        if gateway_running:
            print("\n⚠️  Gateway is currently running")
            print("\n1. STOP Gateway:")
            print("   pkill -f ibgateway")
            print("   # Wait 5 seconds")
            print()
            print("2. START Gateway:")
            print("   cd ~/ibc")
            print("   ./scripts/ibcstart.sh paper")
            print()
            print("3. WAIT for Gateway to fully start (60 seconds)")
            print()
            print("4. TEST the connection:")
            print("   python3 -c \"import socket; s=socket.socket(); s.settimeout(5); s.connect(('127.0.0.1', 4002)); print('✅ Connected!')\"")
        else:
            print("\n1. START Gateway:")
            print("   cd ~/ibc")
            print("   ./scripts/ibcstart.sh paper")
            print()
            print("2. WAIT for Gateway to fully start (60 seconds)")
            print()
            print("3. TEST the connection:")
            print("   python3 -c \"import socket; s=socket.socket(); s.settimeout(5); s.connect(('127.0.0.1', 4002)); print('✅ Connected!')\"")
        
        print("\n" + "=" * 70)
        print("❗ IMPORTANT: Configuration files are only read at Gateway startup")
        print("   You MUST restart Gateway for changes to take effect!")
        print("=" * 70)
    
    def run(self):
        """Run the complete fix process"""
        self.print_header()
        
        # Fix configurations
        self.fix_jts_ini()
        self.fix_ibc_config()
        
        # Check status
        gateway_running = self.check_gateway_running()
        self.check_port_listening()
        
        # Verify
        self.verify_configuration()
        
        # Summary
        self.print_summary()
        self.print_next_steps(gateway_running)
        
        print("\n✅ Configuration fix complete!")


if __name__ == "__main__":
    fixer = GatewayAPIFixer()
    fixer.run()
