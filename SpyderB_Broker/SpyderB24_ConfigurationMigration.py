"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB24_ConfigurationMigration.py
Purpose: Safe Migration from Current Setup to IB Gateway 10.39
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-26 Time: 11:15:00

Module Description:
    Automated migration tool to safely update existing bash configurations
    and IBC settings from the current setup (Gateway 10.37/1012) to the new
    Gateway 10.39 (1039) while preserving custom settings and creating
    comprehensive backups.
"""

import os
import sys
import shutil
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import difflib
import hashlib

# ==============================================================================
# CONSTANTS - MIGRATION CONFIGURATION
# ==============================================================================

# File paths
BASH_IB_PATH = Path.home() / ".bash_ib"
BASHRC_PATH = Path.home() / ".bashrc"
IBC_CONFIG_PATH = Path.home() / "ibc" / "config.ini"
BACKUP_DIR = Path.home() / "spyder_migration_backup"

# Version mappings
VERSION_MIGRATIONS = {
    "TWS_MAJOR_VRSN": {
        "old": ["1012", "1037"],
        "new": "1039"
    },
    "IB_GATEWAY_DIR": {
        "old": ["ibgateway/10.37", "ibgateway/1012"],
        "new": "ibgateway/1039"
    },
    "IB_GATEWAY_VERSION": {
        "old": ["10.37", "10.12"],
        "new": "10.39"
    }
}

# New bash_ib content template
BASH_IB_TEMPLATE = """# ~/.bash_ib — Interactive Brokers Gateway Configuration
# Spyder Autonomous Options Trading System
# Author: Mohamed Talib
# Created: 2025-08-26
# Updated: {timestamp}
# Version: IB Gateway 10.39

# ===============================================================================
# IB GATEWAY CORE SETTINGS - UPGRADED TO 10.39
# ===============================================================================
export TWS_MAJOR_VRSN="1039"
export IB_GATEWAY_VERSION="10.39"
export IBC_PATH="$HOME/ibc"
export IBC_INI="$HOME/ibc/config.ini"
export IB_GATEWAY_DIR="$HOME/Jts/ibgateway/1039"
export IB_GATEWAY_HOME="$HOME/Jts"

# ===============================================================================
# JAVA CONFIGURATION FOR IB GATEWAY 10.39
# ===============================================================================
# Gateway 10.39 works best with Java 8 or 11
export JAVA_HOME="/usr/lib/jvm/java-11-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"

# Java VM options optimized for Gateway 10.39
export JAVA_VM_OPTIONS="-Xms1024m -Xmx4096m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 -XX:+UseStringDeduplication"
export JAVA_OPTS="-Dfile.encoding=UTF-8 -Djava.awt.headless=false -Dswing.aatext=true -Dsun.java2d.xrender=false"

# ===============================================================================
# XVFB CONFIGURATION FOR HEADLESS OPERATION
# ===============================================================================
export DISPLAY=":99"
export XVFB_DISPLAY=":99"
export XAUTHORITY="/tmp/.Xauthority"
export XVFB_OPTIONS="-screen 0 1600x1200x24 -dpi 96 -ac -noreset"

# ===============================================================================
# IB GATEWAY CONNECTION SETTINGS
# ===============================================================================
export IB_GATEWAY_HOST="127.0.0.1"
export IB_GATEWAY_PORT_PAPER="4002"
export IB_GATEWAY_PORT_LIVE="4001"

# Default to paper trading for safety
export IB_GATEWAY_PORT="$IB_GATEWAY_PORT_PAPER"
export IB_TRADING_MODE="paper"

# Connection timeout settings (improved for 10.39)
export IB_CONNECTION_TIMEOUT="60"
export IB_REQUEST_TIMEOUT="30"
export IB_RECONNECT_ATTEMPTS="5"

{client_allocation}

# ===============================================================================
# IB GATEWAY VALIDATION FUNCTION - ENHANCED FOR 10.39
# ===============================================================================
validate_ib_env() {{
    echo "==============================================================================="
    echo "SPYDER IB GATEWAY 10.39 ENVIRONMENT CHECK"
    echo "==============================================================================="
    echo "Gateway Version: $IB_GATEWAY_VERSION"
    echo "TWS Major Version: $TWS_MAJOR_VRSN"
    echo "IBC Path: $IBC_PATH"
    echo "IBC Config: $IBC_INI"
    echo "IB Gateway Directory: $IB_GATEWAY_DIR"
    echo "Java Home: $JAVA_HOME"
    echo "Trading Mode: $IB_TRADING_MODE"
    echo "Gateway Port: $IB_GATEWAY_PORT"
    echo "Display: $DISPLAY"
    echo ""
    
    echo "Directory Validation:"
    [ -d "$IBC_PATH" ] && echo "✅ IBC directory found" || echo "❌ IBC directory missing: $IBC_PATH"
    [ -f "$IBC_INI" ] && echo "✅ IBC config found" || echo "❌ IBC config missing: $IBC_INI"
    [ -d "$IB_GATEWAY_DIR" ] && echo "✅ IB Gateway directory found" || echo "❌ IB Gateway directory missing: $IB_GATEWAY_DIR"
    [ -f "$JAVA_HOME/bin/java" ] && echo "✅ Java found" || echo "❌ Java missing: $JAVA_HOME"
    
    # Check Xvfb
    if command -v Xvfb >/dev/null 2>&1; then
        echo "✅ Xvfb available for headless operation"
    else
        echo "⚠️  Xvfb not installed (required for headless)"
    fi
    echo ""
    
    echo "Port Status:"
    if ss -tuln | grep -q ":$IB_GATEWAY_PORT_PAPER"; then
        echo "✅ Port $IB_GATEWAY_PORT_PAPER (Paper) listening"
    else
        echo "⚠️  Port $IB_GATEWAY_PORT_PAPER (Paper) not listening"
    fi
    
    if ss -tuln | grep -q ":$IB_GATEWAY_PORT_LIVE"; then
        echo "✅ Port $IB_GATEWAY_PORT_LIVE (Live) listening"
    else
        echo "⚠️  Port $IB_GATEWAY_PORT_LIVE (Live) not listening"
    fi
    echo ""
    
    echo "Java Version:"
    if [ -f "$JAVA_HOME/bin/java" ]; then
        "$JAVA_HOME/bin/java" -version 2>&1 | head -3
    else
        echo "Java not found at $JAVA_HOME"
    fi
    echo ""
    
    echo "Client ID Allocation:"
    echo "Range: $IB_CLIENT_ID_START to $IB_CLIENT_ID_END"
    echo ""
}}

{existing_functions}

# ===============================================================================
# NEW GATEWAY 10.39 FUNCTIONS
# ===============================================================================
# Start Xvfb for headless operation
start_xvfb() {{
    if ! pgrep Xvfb > /dev/null; then
        echo "Starting Xvfb virtual display..."
        Xvfb $XVFB_DISPLAY $XVFB_OPTIONS &
        sleep 2
        echo "✅ Xvfb started on display $XVFB_DISPLAY"
    else
        echo "Xvfb already running"
    fi
}}

# Stop Xvfb
stop_xvfb() {{
    if pgrep Xvfb > /dev/null; then
        echo "Stopping Xvfb..."
        pkill Xvfb
        echo "✅ Xvfb stopped"
    else
        echo "Xvfb not running"
    fi
}}

# Start IB Gateway with IBC automation
start_ib_gateway() {{
    echo "🚀 Starting IB Gateway 10.39..."
    
    # Check if already running
    if ib_gateway_running; then
        echo "⚠️  Gateway already running"
        return 1
    fi
    
    # Start Xvfb if needed
    start_xvfb
    
    # Start Gateway
    cd "$SPYDER_HOME"
    python3 SpyderB_Broker/SpyderB21_GatewayStartupAutomation.py
}}

# ===============================================================================
# ENHANCED ALIASES FOR GATEWAY 10.39
# ===============================================================================
alias ib-start='start_ib_gateway'
alias ib-stop='pkill -f ibgateway'
alias xvfb-start='start_xvfb'
alias xvfb-stop='stop_xvfb'
alias xvfb-status='pgrep Xvfb && echo "Xvfb running" || echo "Xvfb not running"'

# Migration check
alias ib-migrate-check='echo "Current version: $TWS_MAJOR_VRSN (should be 1039)"'

{safety_warnings}
"""

# Enhanced IBC configuration template
IBC_CONFIG_TEMPLATE = """# IBC Configuration for IB Gateway 10.39
# Generated by Spyder Migration Tool
# {timestamp}

# ===============================================================================
# LOGIN CREDENTIALS (PRESERVED FROM ORIGINAL)
# ===============================================================================
{credentials}

# ===============================================================================
# GATEWAY SETTINGS
# ===============================================================================
Gateway=yes
TWS=no
IbDir={ib_dir}

# ===============================================================================
# API CONFIGURATION
# ===============================================================================
OverrideTwsApiPort={port}
AcceptIncomingConnectionAction=accept
AllowBlindTrading=yes
ReadOnlyLogin=no
AcceptNonBrokerageAccountWarning=yes

# ===============================================================================
# SESSION HANDLING
# ===============================================================================
ExistingSessionDetectedAction=primary
StoreSettingsOnServer=yes
MinimizeMainWindow=yes
ConfirmExitApplication=no

# ===============================================================================
# AUTO-RESTART CONFIGURATION (ENHANCED)
# ===============================================================================
# Daily restart at 11:45 PM ET
AutoRestartTime=23:45

# Weekly cold restart Sunday at 2:00 AM ET (after IB maintenance)
ColdRestartTime=02:00 Sunday

# ===============================================================================
# DIALOG HANDLING (COMPREHENSIVE)
# ===============================================================================
DismissPasswordExpiryWarning=yes
DismissNSEComplianceNotice=yes
DismissHSBCDisclaimer=yes
SaveTwsSettingsAt=EveryChange

# ===============================================================================
# ERROR HANDLING
# ===============================================================================
ExitAfterSecondFactorAuthenticationTimeout=no
SecondFactorAuthenticationTimeout=180
ReloginAfterSecondFactorAuthenticationTimeout=yes

# ===============================================================================
# LOGGING
# ===============================================================================
LogToConsole=yes
LogFile={log_path}
LogLevel=INFO
LogComponents=yes
"""

# ==============================================================================
# MIGRATION MANAGER CLASS
# ==============================================================================

class ConfigurationMigrationManager:
    """
    Manages safe migration from current IB Gateway setup to 10.39.
    
    This manager:
    - Creates comprehensive backups
    - Preserves custom settings
    - Updates version-specific configurations
    - Validates migration results
    - Provides rollback capability
    """
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize migration manager.
        
        Args:
            dry_run: If True, show changes without applying them
        """
        self.dry_run = dry_run
        self.logger = self._setup_logger()
        self.backup_dir = BACKUP_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.changes_made = []
        
    def _setup_logger(self) -> logging.Logger:
        """Setup migration logger"""
        logger = logging.getLogger("Migration")
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not logger.handlers:
            logger.addHandler(handler)
        
        return logger
    
    # ==========================================================================
    # BACKUP OPERATIONS
    # ==========================================================================
    
    def create_backup(self) -> bool:
        """Create comprehensive backup of all configuration files"""
        try:
            self.logger.info(f"Creating backup in {self.backup_dir}")
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Files to backup
            files_to_backup = [
                (BASH_IB_PATH, "bash_ib.bak"),
                (BASHRC_PATH, "bashrc.bak"),
                (IBC_CONFIG_PATH, "ibc_config.ini.bak"),
                (Path.home() / "Jts" / "jts.ini", "jts.ini.bak")
            ]
            
            for source, dest_name in files_to_backup:
                if source.exists():
                    dest = self.backup_dir / dest_name
                    shutil.copy2(source, dest)
                    self.logger.info(f"✅ Backed up: {source.name}")
            
            # Save migration metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "original_version": self._detect_current_version(),
                "target_version": "10.39",
                "files_backed_up": [str(f[0]) for f in files_to_backup if f[0].exists()]
            }
            
            with open(self.backup_dir / "migration_metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info("✅ Backup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            return False
    
    def _detect_current_version(self) -> str:
        """Detect current IB Gateway version from configuration"""
        if BASH_IB_PATH.exists():
            content = BASH_IB_PATH.read_text()
            match = re.search(r'TWS_MAJOR_VRSN="(\d+)"', content)
            if match:
                return match.group(1)
        return "unknown"
    
    # ==========================================================================
    # MIGRATION OPERATIONS
    # ==========================================================================
    
    def migrate_bash_ib(self) -> bool:
        """Migrate .bash_ib file to Gateway 10.39"""
        self.logger.info("Migrating ~/.bash_ib...")
        
        try:
            # Read existing file
            if BASH_IB_PATH.exists():
                old_content = BASH_IB_PATH.read_text()
                
                # Extract client allocation section
                client_section = self._extract_client_allocation(old_content)
                
                # Extract custom functions
                custom_functions = self._extract_custom_functions(old_content)
                
                # Extract safety warnings
                safety_warnings = self._extract_safety_warnings(old_content)
            else:
                client_section = self._get_default_client_allocation()
                custom_functions = ""
                safety_warnings = ""
            
            # Generate new content
            new_content = BASH_IB_TEMPLATE.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                client_allocation=client_section,
                existing_functions=custom_functions,
                safety_warnings=safety_warnings
            )
            
            # Show diff if in dry run
            if self.dry_run:
                self._show_diff(old_content if BASH_IB_PATH.exists() else "", 
                              new_content, ".bash_ib")
                return True
            
            # Write new content
            BASH_IB_PATH.write_text(new_content)
            self.changes_made.append("Updated ~/.bash_ib to Gateway 10.39")
            self.logger.info("✅ ~/.bash_ib migrated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to migrate .bash_ib: {e}")
            return False
    
    def _extract_client_allocation(self, content: str) -> str:
        """Extract client ID allocation section from existing config"""
        pattern = r'# CLIENT ID ALLOCATION.*?(?=\n#|$)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(0).strip()
        
        return self._get_default_client_allocation()
    
    def _get_default_client_allocation(self) -> str:
        """Get default client allocation configuration"""
        return """# ===============================================================================
# CLIENT ID ALLOCATION STRATEGY
# ===============================================================================
export IB_CLIENT_ID_START="1"
export IB_CLIENT_ID_END="11"

# Specific client assignments
export IB_ORDER_EXECUTION_CLIENT="1"
export IB_MASTER_CLIENT="2"
export IB_DASHBOARD_CLIENT="3"
export IB_MARKET_DATA_CLIENT="4"
export IB_RISK_MANAGEMENT_CLIENT="5"
export IB_PORTFOLIO_CLIENT="6"
export IB_ANALYTICS_CLIENT="7"
export IB_BACKUP_CLIENT="8"
export IB_TESTING_CLIENT="9"
export IB_MONITORING_CLIENT="10"
export IB_NEWSFEED_CLIENT="11\""""
    
    def _extract_custom_functions(self, content: str) -> str:
        """Extract custom functions from existing config"""
        functions = []
        
        # Look for specific function patterns
        patterns = [
            r'(show_client_allocation\(\).*?\n})',
            r'(ib_gateway_running\(\).*?\n})',
            r'(ib_gateway_status\(\).*?\n})',
            r'(spyder_system_status\(\).*?\n})',
            r'(test_ib_connection\(\).*?\n})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                functions.append(match.group(1))
        
        return "\n\n".join(functions)
    
    def _extract_safety_warnings(self, content: str) -> str:
        """Extract safety warnings section"""
        pattern = r'# SAFETY WARNINGS.*?(?=# END|$)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(0).strip()
        
        return """# ===============================================================================
# SAFETY WARNINGS
# ===============================================================================
# Show trading mode warning
if [ "$IB_TRADING_MODE" = "live" ]; then
    echo ""
    echo "⚠️  ⚠️  ⚠️  WARNING: LIVE TRADING MODE ENABLED  ⚠️  ⚠️  ⚠️"
    echo "Real money trades will be executed!"
    echo "Use 'ib-paper' to switch to paper trading"
    echo ""
fi"""
    
    def migrate_ibc_config(self) -> bool:
        """Migrate IBC configuration with enhanced settings"""
        self.logger.info("Migrating ~/ibc/config.ini...")
        
        try:
            # Read existing config to preserve credentials
            credentials_section = ""
            port = "4002"  # Default to paper
            
            if IBC_CONFIG_PATH.exists():
                old_content = IBC_CONFIG_PATH.read_text()
                
                # Extract credentials (being careful with sensitive data)
                for line in old_content.split('\n'):
                    if line.startswith(('IbLoginId=', 'IbPassword=', 'TradingMode=')):
                        credentials_section += line + '\n'
                
                # Extract port if specified
                port_match = re.search(r'OverrideTwsApiPort=(\d+)', old_content)
                if port_match:
                    port = port_match.group(1)
            
            # Generate new config
            new_content = IBC_CONFIG_TEMPLATE.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                credentials=credentials_section.strip(),
                ib_dir="/home/adam/Jts",  # Using actual path from provided config
                port=port,
                log_path="$HOME/spyder_logs/ibc/ibc.log"
            )
            
            if self.dry_run:
                self.logger.info("DRY RUN - Would update IBC config")
                # Don't show diff for security (contains password)
                self.logger.info("IBC config would be updated with enhanced settings")
                return True
            
            # Ensure directory exists
            IBC_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            
            # Write new config
            IBC_CONFIG_PATH.write_text(new_content)
            
            # Set secure permissions
            os.chmod(IBC_CONFIG_PATH, 0o600)
            
            self.changes_made.append("Updated ~/ibc/config.ini with enhanced settings")
            self.logger.info("✅ IBC config migrated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to migrate IBC config: {e}")
            return False
    
    def update_gateway_directories(self) -> bool:
        """Create necessary directories for Gateway 10.39"""
        self.logger.info("Setting up Gateway 10.39 directories...")
        
        directories = [
            Path.home() / "Jts" / "ibgateway" / "1039",
            Path.home() / "spyder_logs" / "ibc",
            Path.home() / "spyder_logs" / "gateway",
            Path.home() / "ibc"
        ]
        
        for directory in directories:
            if not directory.exists():
                if self.dry_run:
                    self.logger.info(f"DRY RUN - Would create: {directory}")
                else:
                    directory.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"✅ Created: {directory}")
        
        return True
    
    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    
    def validate_migration(self) -> bool:
        """Validate the migration was successful"""
        self.logger.info("Validating migration...")
        
        issues = []
        
        # Check bash_ib
        if BASH_IB_PATH.exists():
            content = BASH_IB_PATH.read_text()
            if 'TWS_MAJOR_VRSN="1039"' not in content:
                issues.append("TWS_MAJOR_VRSN not updated in .bash_ib")
        else:
            issues.append(".bash_ib file not found")
        
        # Check IBC config
        if not IBC_CONFIG_PATH.exists():
            issues.append("IBC config not found")
        
        # Check directories
        gateway_dir = Path.home() / "Jts" / "ibgateway" / "1039"
        if not gateway_dir.exists():
            issues.append(f"Gateway directory not created: {gateway_dir}")
        
        if issues:
            self.logger.error("❌ Validation failed:")
            for issue in issues:
                self.logger.error(f"  • {issue}")
            return False
        
        self.logger.info("✅ Migration validated successfully")
        return True
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    
    def _show_diff(self, old: str, new: str, filename: str):
        """Show diff between old and new content"""
        print(f"\n{'=' * 60}")
        print(f"Changes for {filename}:")
        print('=' * 60)
        
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"{filename}.old",
            tofile=f"{filename}.new",
            lineterm=''
        )
        
        for line in diff:
            if line.startswith('+'):
                print(f"\033[92m{line}\033[0m", end='')  # Green
            elif line.startswith('-'):
                print(f"\033[91m{line}\033[0m", end='')  # Red
            else:
                print(line, end='')
        
        print()
    
    def rollback(self):
        """Rollback to backed up configuration"""
        self.logger.info("Rolling back migration...")
        
        if not self.backup_dir.exists():
            self.logger.error("No backup found to rollback")
            return False
        
        try:
            # Restore files
            for backup_file in self.backup_dir.glob("*.bak"):
                original_name = backup_file.stem
                
                if original_name == "bash_ib":
                    target = BASH_IB_PATH
                elif original_name == "bashrc":
                    target = BASHRC_PATH
                elif original_name == "ibc_config.ini":
                    target = IBC_CONFIG_PATH
                else:
                    continue
                
                shutil.copy2(backup_file, target)
                self.logger.info(f"✅ Restored: {target.name}")
            
            self.logger.info("✅ Rollback completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False
    
    # ==========================================================================
    # MAIN MIGRATION PROCESS
    # ==========================================================================
    
    def run_migration(self) -> bool:
        """Run complete migration process"""
        self.logger.info("=" * 60)
        self.logger.info("IB GATEWAY 10.39 MIGRATION TOOL")
        self.logger.info("=" * 60)
        
        if self.dry_run:
            self.logger.info("🔍 Running in DRY RUN mode - no changes will be made")
        
        # Step 1: Create backup
        if not self.dry_run:
            if not self.create_backup():
                self.logger.error("Backup failed - aborting migration")
                return False
        
        # Step 2: Migrate configurations
        success = True
        
        if not self.migrate_bash_ib():
            success = False
        
        if not self.migrate_ibc_config():
            success = False
        
        if not self.update_gateway_directories():
            success = False
        
        # Step 3: Validate if not dry run
        if not self.dry_run and success:
            success = self.validate_migration()
        
        # Step 4: Report results
        self.logger.info("\n" + "=" * 60)
        if success:
            self.logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
            
            if not self.dry_run:
                self.logger.info(f"\nBackup saved to: {self.backup_dir}")
                self.logger.info("\nChanges made:")
                for change in self.changes_made:
                    self.logger.info(f"  • {change}")
                
                self.logger.info("\n📝 Next steps:")
                self.logger.info("1. Run: source ~/.bash_ib")
                self.logger.info("2. Run: validate_ib_env")
                self.logger.info("3. Download IB Gateway 10.39 if not already installed")
                self.logger.info("4. Test with: start_ib_gateway")
        else:
            self.logger.error("❌ MIGRATION FAILED")
            if not self.dry_run:
                self.logger.info("Run with --rollback to restore original configuration")
        
        self.logger.info("=" * 60)
        
        return success

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate IB Gateway configuration to version 10.39"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making actual changes"
    )
    
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback to previous configuration"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force migration without confirmation"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    # Create migration manager
    manager = ConfigurationMigrationManager(dry_run=args.dry_run)
    
    if args.rollback:
        print("🔄 Rolling back migration...")
        if manager.rollback():
            print("✅ Rollback completed")
            sys.exit(0)
        else:
            print("❌ Rollback failed")
            sys.exit(1)
    
    # Confirm migration unless forced
    if not args.force and not args.dry_run:
        print("\n⚠️  This will migrate your IB Gateway configuration to version 10.39")
        print("   A backup will be created before any changes are made.")
        response = input("\nContinue? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled")
            sys.exit(0)
    
    # Run migration
    if manager.run_migration():
        sys.exit(0)
    else:
        sys.exit(1)
