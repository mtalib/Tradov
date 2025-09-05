"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB23_BashrcConfiguration.py
Purpose: Automated Bashrc Configuration for IB Gateway 10.39
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-26 Time: 11:00:00

Module Description:
    Automated configuration management for .bashrc environment setup specific
    to IB Gateway 10.39 and the Spyder trading system. Handles environment
    variables, paths, aliases, and system optimizations required for stable
    Gateway operation on Ubuntu 25.04 with Wayland/Xvfb support.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
import hashlib

# ==============================================================================
# CONSTANTS - ENVIRONMENT CONFIGURATION FOR 10.39
# ==============================================================================

# IB Gateway 10.39 Environment Variables
IB_ENV_VARS = {
    # Version Configuration
    "TWS_MAJOR_VRSN": "1039",
    "IB_GATEWAY_VERSION": "10.39",
    "IB_GATEWAY_BUILD": "10.39.1e",
    
    # Directory Paths
    "IB_GATEWAY_HOME": "$HOME/Jts",
    "IB_GATEWAY_DIR": "$HOME/Jts/ibgateway/1039",
    "IBC_PATH": "$HOME/ibc",
    "IBC_INI": "$HOME/ibc/config.ini",
    
    # Spyder Paths
    "SPYDER_HOME": "$HOME/spyder",
    "SPYDER_LOGS": "$HOME/spyder_logs",
    "SPYDER_CONFIG": "$HOME/spyder/config",
    "SPYDER_DATA": "$HOME/spyder/data",
    
    # Display Configuration
    "DISPLAY": ":0",
    "XAUTHORITY": "/tmp/.Xauthority",
    
    # Java Configuration
    "JAVA_HOME": "/usr/lib/jvm/java-8-openjdk-amd64",
    "_JAVA_OPTIONS": "-Xmx4096m -Xms1024m -XX:+UseG1GC",
    
    # API Configuration
    "IB_API_PORT_PAPER": "4002",
    "IB_API_PORT_LIVE": "4001",
    "IB_CONTROLLER_PORT": "4003",
    
    # Python Path
    "PYTHONPATH": "$PYTHONPATH:$SPYDER_HOME",
    
    # Timezone (critical for trading)
    "TZ": "America/New_York"
}

# System Aliases for Spyder Trading
SPYDER_ALIASES = {
    # Gateway Control
    "ibstart": "python3 $SPYDER_HOME/SpyderB_Broker/SpyderB21_GatewayStartupAutomation.py",
    "ibstop": "pkill -f ibgateway",
    "ibstatus": "ps aux | grep -E 'ibgateway|IBC' | grep -v grep",
    "iblog": "tail -f $SPYDER_LOGS/ibc/gateway_startup_*.log",
    
    # Spyder System
    "spyder": "cd $SPYDER_HOME && python3 SpyderA_Core/SpyderA01_Main.py",
    "spyder-test": "python3 $SPYDER_HOME/SpyderB_Broker/SpyderB22_IntegrationTestSuite.py",
    "spyder-config": "python3 $SPYDER_HOME/SpyderB_Broker/SpyderB19_GatewayConfiguration.py",
    "spyder-logs": "cd $SPYDER_LOGS && ls -la",
    
    # Quick Navigation
    "cdspyder": "cd $SPYDER_HOME",
    "cdib": "cd $IB_GATEWAY_HOME",
    "cdibc": "cd $IBC_PATH",
    "cdlogs": "cd $SPYDER_LOGS",
    
    # Process Management
    "xvfb-start": "Xvfb :0 -screen 0 1600x1200x24 -dpi 96 -ac -noreset &",
    "xvfb-stop": "pkill Xvfb",
    "xvfb-status": "ps aux | grep Xvfb | grep -v grep",
    
    # Development
    "spyder-edit": "code $SPYDER_HOME",
    "spyder-pull": "cd $SPYDER_HOME && git pull",
    "spyder-backup": "tar -czf ~/spyder_backup_$(date +%Y%m%d_%H%M%S).tar.gz $SPYDER_HOME"
}

# Shell Functions for Advanced Operations
SHELL_FUNCTIONS = """
# ==============================================================================
# SPYDER TRADING SYSTEM FUNCTIONS
# ==============================================================================

# Function to start IB Gateway with monitoring
spyder_gateway_start() {
    echo "🚀 Starting IB Gateway 10.39..."
    
    # Check if already running
    if pgrep -f ibgateway > /dev/null; then
        echo "⚠️  Gateway already running"
        return 1
    fi
    
    # Start Xvfb if not running
    if ! pgrep Xvfb > /dev/null; then
        echo "Starting Xvfb display..."
        Xvfb :0 -screen 0 1600x1200x24 -dpi 96 -ac -noreset &
        sleep 2
    fi
    
    # Set display
    export DISPLAY=:0
    
    # Start Gateway
    python3 $SPYDER_HOME/SpyderB_Broker/SpyderB21_GatewayStartupAutomation.py
}

# Function to check all Spyder components
spyder_health_check() {
    echo "🏥 Spyder System Health Check"
    echo "=============================="
    
    # Check Python
    echo -n "Python: "
    python3 --version
    
    # Check Java
    echo -n "Java: "
    java -version 2>&1 | head -n 1
    
    # Check IB Gateway
    echo -n "IB Gateway: "
    if [ -d "$IB_GATEWAY_DIR" ]; then
        echo "✅ Installed (v$IB_GATEWAY_VERSION)"
    else
        echo "❌ Not found"
    fi
    
    # Check IBC
    echo -n "IBC: "
    if [ -f "$IBC_PATH/IBC.jar" ]; then
        echo "✅ Installed"
    else
        echo "❌ Not found"
    fi
    
    # Check Xvfb
    echo -n "Xvfb: "
    if pgrep Xvfb > /dev/null; then
        echo "✅ Running"
    else
        echo "⚠️  Not running"
    fi
    
    # Check Gateway Process
    echo -n "Gateway Process: "
    if pgrep -f ibgateway > /dev/null; then
        echo "✅ Running"
    else
        echo "⚠️  Not running"
    fi
    
    # Check API Port
    echo -n "API Port $IB_API_PORT_PAPER: "
    if nc -z localhost $IB_API_PORT_PAPER 2>/dev/null; then
        echo "✅ Open"
    else
        echo "⚠️  Closed"
    fi
    
    # Check Memory
    echo -n "Memory Available: "
    free -h | awk '/^Mem:/ {print $7}'
    
    echo "=============================="
}

# Function to tail all relevant logs
spyder_logs() {
    echo "📜 Tailing Spyder logs..."
    
    # Create a tmux session with multiple panes for different logs
    tmux new-session -d -s spyder_logs
    tmux send-keys -t spyder_logs "tail -f $SPYDER_LOGS/ibc/gateway_startup_*.log" C-m
    tmux split-window -h -t spyder_logs
    tmux send-keys -t spyder_logs "tail -f $SPYDER_LOGS/gateway/*.log" C-m
    tmux split-window -v -t spyder_logs
    tmux send-keys -t spyder_logs "tail -f $SPYDER_LOGS/spyder_*.log" C-m
    tmux attach-session -t spyder_logs
}

# Function to backup Spyder configuration
spyder_backup() {
    BACKUP_DIR="$HOME/spyder_backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    echo "📦 Creating Spyder backup in $BACKUP_DIR..."
    
    # Backup configurations
    cp -r "$SPYDER_CONFIG" "$BACKUP_DIR/"
    cp "$HOME/.bashrc" "$BACKUP_DIR/bashrc_backup"
    cp -r "$IBC_PATH" "$BACKUP_DIR/ibc_backup"
    
    # Create archive
    tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
    rm -rf "$BACKUP_DIR"
    
    echo "✅ Backup created: $BACKUP_DIR.tar.gz"
}

# Function to update Spyder system
spyder_update() {
    echo "🔄 Updating Spyder Trading System..."
    
    cd "$SPYDER_HOME"
    
    # Create backup first
    spyder_backup
    
    # Pull latest changes
    git pull origin main
    
    # Update Python dependencies
    pip3 install -r requirements.txt --upgrade
    
    # Run tests
    python3 SpyderB_Broker/SpyderB22_IntegrationTestSuite.py
    
    echo "✅ Update complete"
}
"""

# Bashrc Section Markers
BASHRC_MARKERS = {
    "start": "# >>> SPYDER TRADING SYSTEM START >>>",
    "end": "# <<< SPYDER TRADING SYSTEM END <<<"
}

# ==============================================================================
# CONFIGURATION DATA CLASSES
# ==============================================================================

@dataclass
class BashrcConfig:
    """Bashrc configuration settings"""
    backup_enabled: bool = True
    backup_dir: Path = field(default_factory=lambda: Path.home() / "bashrc_backups")
    bashrc_path: Path = field(default_factory=lambda: Path.home() / ".bashrc")
    test_mode: bool = False
    force_update: bool = False
    
    def get_backup_path(self) -> Path:
        """Generate backup file path with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.backup_dir / f"bashrc_backup_{timestamp}"

@dataclass
class ValidationResult:
    """Configuration validation result"""
    is_valid: bool
    missing_vars: List[str] = field(default_factory=list)
    incorrect_vars: Dict[str, str] = field(default_factory=dict)
    missing_aliases: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def has_issues(self) -> bool:
        return not self.is_valid or self.warnings

# ==============================================================================
# BASHRC CONFIGURATION MANAGER
# ==============================================================================

class BashrcConfigurationManager:
    """
    Manages .bashrc configuration for Spyder Trading System.
    
    This manager provides:
    - Automated environment variable configuration
    - Alias and function installation
    - Safe backup and restore functionality
    - Configuration validation and verification
    - Migration from older versions
    """
    
    def __init__(self, config: Optional[BashrcConfig] = None):
        """Initialize bashrc configuration manager"""
        self.config = config or BashrcConfig()
        self.logger = self._setup_logger()
        
        # Ensure backup directory exists
        if self.config.backup_enabled:
            self.config.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _setup_logger(self) -> logging.Logger:
        """Setup module logger"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    # ==========================================================================
    # BACKUP AND RESTORE
    # ==========================================================================
    
    def backup_bashrc(self) -> Optional[Path]:
        """
        Create backup of current .bashrc file.
        
        Returns:
            Path to backup file or None if backup disabled
        """
        if not self.config.backup_enabled:
            return None
        
        if not self.config.bashrc_path.exists():
            self.logger.warning("No .bashrc file to backup")
            return None
        
        backup_path = self.config.get_backup_path()
        
        try:
            shutil.copy2(self.config.bashrc_path, backup_path)
            self.logger.info(f"✅ Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            return None
    
    def restore_bashrc(self, backup_path: Optional[Path] = None) -> bool:
        """
        Restore .bashrc from backup.
        
        Args:
            backup_path: Specific backup to restore (latest if None)
            
        Returns:
            bool: True if restored successfully
        """
        if backup_path is None:
            # Find latest backup
            backups = sorted(self.config.backup_dir.glob("bashrc_backup_*"))
            if not backups:
                self.logger.error("No backups found")
                return False
            backup_path = backups[-1]
        
        if not backup_path.exists():
            self.logger.error(f"Backup not found: {backup_path}")
            return False
        
        try:
            shutil.copy2(backup_path, self.config.bashrc_path)
            self.logger.info(f"✅ Restored from: {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return False
    
    # ==========================================================================
    # CONFIGURATION MANAGEMENT
    # ==========================================================================
    
    def read_bashrc(self) -> str:
        """Read current .bashrc content"""
        if not self.config.bashrc_path.exists():
            self.logger.warning(".bashrc not found - creating new file")
            return ""
        
        return self.config.bashrc_path.read_text()
    
    def write_bashrc(self, content: str) -> bool:
        """
        Write content to .bashrc file.
        
        Args:
            content: New bashrc content
            
        Returns:
            bool: True if written successfully
        """
        try:
            self.config.bashrc_path.write_text(content)
            self.logger.info("✅ .bashrc updated")
            return True
        except Exception as e:
            self.logger.error(f"Failed to write .bashrc: {e}")
            return False
    
    def has_spyder_config(self) -> bool:
        """Check if Spyder configuration already exists"""
        content = self.read_bashrc()
        return BASHRC_MARKERS["start"] in content
    
    def remove_spyder_config(self, content: str) -> str:
        """
        Remove existing Spyder configuration from content.
        
        Args:
            content: Bashrc content
            
        Returns:
            Content without Spyder configuration
        """
        if not self.has_spyder_config():
            return content
        
        # Find and remove section between markers
        pattern = re.compile(
            f"{re.escape(BASHRC_MARKERS['start'])}.*?{re.escape(BASHRC_MARKERS['end'])}",
            re.DOTALL
        )
        
        cleaned = re.sub(pattern, "", content)
        return cleaned.strip() + "\n"
    
    def generate_spyder_config(self) -> str:
        """
        Generate Spyder configuration section.
        
        Returns:
            Complete configuration string
        """
        lines = []
        lines.append(BASHRC_MARKERS["start"])
        lines.append(f"# Generated by Spyder Trading System on {datetime.now()}")
        lines.append(f"# IB Gateway Version: {IB_ENV_VARS['IB_GATEWAY_VERSION']}")
        lines.append("")
        
        # Environment Variables
        lines.append("# Environment Variables")
        lines.append("# " + "=" * 40)
        for key, value in IB_ENV_VARS.items():
            lines.append(f'export {key}="{value}"')
        lines.append("")
        
        # Aliases
        lines.append("# Aliases")
        lines.append("# " + "=" * 40)
        for alias, command in SPYDER_ALIASES.items():
            lines.append(f'alias {alias}="{command}"')
        lines.append("")
        
        # Shell Functions
        lines.append("# Shell Functions")
        lines.append("# " + "=" * 40)
        lines.append(SHELL_FUNCTIONS.strip())
        lines.append("")
        
        # Additional Configuration
        lines.append("# Additional Configuration")
        lines.append("# " + "=" * 40)
        lines.append("# Set umask for secure file creation")
        lines.append("umask 077")
        lines.append("")
        lines.append("# Enable color support for ls")
        lines.append("alias ls='ls --color=auto'")
        lines.append("alias ll='ls -alF'")
        lines.append("")
        lines.append("# History settings")
        lines.append("export HISTSIZE=10000")
        lines.append("export HISTFILESIZE=20000")
        lines.append("export HISTCONTROL=ignoreboth")
        lines.append("")
        
        lines.append(BASHRC_MARKERS["end"])
        
        return "\n".join(lines)
    
    def install_configuration(self) -> bool:
        """
        Install Spyder configuration to .bashrc.
        
        Returns:
            bool: True if installed successfully
        """
        try:
            # Create backup
            if self.config.backup_enabled:
                backup_path = self.backup_bashrc()
                if backup_path:
                    self.logger.info(f"Backup saved to: {backup_path}")
            
            # Read current content
            content = self.read_bashrc()
            
            # Remove existing configuration if present
            if self.has_spyder_config():
                if not self.config.force_update:
                    self.logger.warning("Spyder configuration already exists")
                    response = input("Replace existing configuration? (y/N): ")
                    if response.lower() != 'y':
                        self.logger.info("Installation cancelled")
                        return False
                
                content = self.remove_spyder_config(content)
                self.logger.info("Removed existing configuration")
            
            # Generate new configuration
            spyder_config = self.generate_spyder_config()
            
            # Append configuration
            new_content = content + "\n" + spyder_config
            
            # Write to file (or test mode)
            if self.config.test_mode:
                self.logger.info("TEST MODE - Configuration not written")
                print("\n" + "=" * 60)
                print("Generated Configuration:")
                print("=" * 60)
                print(spyder_config)
                print("=" * 60)
                return True
            else:
                if self.write_bashrc(new_content):
                    self.logger.info("✅ Configuration installed successfully")
                    self.logger.info("Run 'source ~/.bashrc' to apply changes")
                    return True
                else:
                    return False
                    
        except Exception as e:
            self.logger.error(f"Installation failed: {e}")
            return False
    
    # ==========================================================================
    # VALIDATION AND VERIFICATION
    # ==========================================================================
    
    def validate_configuration(self) -> ValidationResult:
        """
        Validate current bashrc configuration.
        
        Returns:
            ValidationResult with details
        """
        result = ValidationResult(is_valid=True)
        
        # Check if configuration exists
        if not self.has_spyder_config():
            result.is_valid = False
            result.warnings.append("Spyder configuration not found in .bashrc")
            return result
        
        content = self.read_bashrc()
        
        # Check environment variables
        for var, expected_value in IB_ENV_VARS.items():
            pattern = f'export {var}="([^"]*)"'
            match = re.search(pattern, content)
            
            if not match:
                result.missing_vars.append(var)
                result.is_valid = False
            elif match.group(1) != expected_value:
                # Allow for variable expansion
                if not ("$" in expected_value and "$" in match.group(1)):
                    result.incorrect_vars[var] = f"Found: {match.group(1)}, Expected: {expected_value}"
        
        # Check aliases
        for alias in SPYDER_ALIASES.keys():
            pattern = f'alias {alias}='
            if pattern not in content:
                result.missing_aliases.append(alias)
        
        # Check for shell functions
        critical_functions = ["spyder_gateway_start", "spyder_health_check"]
        for func in critical_functions:
            if f"{func}()" not in content:
                result.warnings.append(f"Function '{func}' not found")
        
        return result
    
    def verify_environment(self) -> Dict[str, Any]:
        """
        Verify environment variables are set correctly.
        
        Returns:
            Dictionary with verification results
        """
        results = {}
        
        for var, expected in IB_ENV_VARS.items():
            actual = os.getenv(var)
            
            # Expand expected value if it contains variables
            if "$" in expected:
                expanded = os.path.expandvars(expected)
            else:
                expanded = expected
            
            results[var] = {
                "expected": expected,
                "actual": actual,
                "matches": actual == expanded if actual else False
            }
        
        return results
    
    def apply_configuration(self) -> bool:
        """
        Apply configuration by sourcing .bashrc.
        
        Returns:
            bool: True if applied successfully
        """
        try:
            # Note: This won't affect the current Python process environment
            # but will work for subprocesses
            result = subprocess.run(
                ["bash", "-c", f"source {self.config.bashrc_path} && env"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.logger.info("✅ Configuration sourced successfully")
                self.logger.info("Note: Restart shell or run 'source ~/.bashrc' for full effect")
                return True
            else:
                self.logger.error(f"Failed to source .bashrc: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to apply configuration: {e}")
            return False
    
    # ==========================================================================
    # MIGRATION UTILITIES
    # ==========================================================================
    
    def migrate_from_1037(self) -> bool:
        """
        Migrate configuration from Gateway 10.37 to 10.39.
        
        Returns:
            bool: True if migrated successfully
        """
        self.logger.info("🔄 Migrating from Gateway 10.37 to 10.39...")
        
        content = self.read_bashrc()
        
        if not content:
            self.logger.warning("No .bashrc content to migrate")
            return False
        
        # Backup before migration
        if self.config.backup_enabled:
            backup_path = self.backup_bashrc()
            self.logger.info(f"Pre-migration backup: {backup_path}")
        
        # Replace version numbers
        replacements = [
            ('TWS_MAJOR_VRSN="1037"', 'TWS_MAJOR_VRSN="1039"'),
            ('TWS_MAJOR_VRSN="1012"', 'TWS_MAJOR_VRSN="1039"'),  # Old version
            ('IB_GATEWAY_VERSION="10.37"', 'IB_GATEWAY_VERSION="10.39"'),
            ('/ibgateway/1037', '/ibgateway/1039'),
            ('/ibgateway/1012', '/ibgateway/1039'),
        ]
        
        modified = False
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                modified = True
                self.logger.info(f"Replaced: {old} → {new}")
        
        if modified:
            if self.write_bashrc(content):
                self.logger.info("✅ Migration completed successfully")
                return True
            else:
                self.logger.error("Failed to write migrated configuration")
                return False
        else:
            self.logger.info("No migration changes needed")
            return True
    
    # ==========================================================================
    # UTILITY FUNCTIONS
    # ==========================================================================
    
    def show_current_config(self):
        """Display current Spyder configuration from .bashrc"""
        if not self.has_spyder_config():
            print("❌ No Spyder configuration found in .bashrc")
            return
        
        content = self.read_bashrc()
        
        # Extract Spyder section
        pattern = re.compile(
            f"{re.escape(BASHRC_MARKERS['start'])}(.*?){re.escape(BASHRC_MARKERS['end'])}",
            re.DOTALL
        )
        
        match = pattern.search(content)
        if match:
            print("=" * 60)
            print("Current Spyder Configuration in .bashrc")
            print("=" * 60)
            print(match.group(0))
            print("=" * 60)
    
    def create_setup_script(self, filepath: Optional[Path] = None) -> bool:
        """
        Create standalone setup script.
        
        Args:
            filepath: Output file path
            
        Returns:
            bool: True if created successfully
        """
        filepath = filepath or Path("setup_spyder_env.sh")
        
        script_content = f"""#!/bin/bash
# Spyder Trading System Environment Setup Script
# Generated on {datetime.now()}
# IB Gateway Version: {IB_ENV_VARS['IB_GATEWAY_VERSION']}

set -e  # Exit on error

echo "🚀 Setting up Spyder Trading System environment..."

# Check if running with bash
if [ -z "$BASH_VERSION" ]; then
    echo "❌ This script must be run with bash"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p ~/Jts/ibgateway/1039
mkdir -p ~/ibc
mkdir -p ~/spyder
mkdir -p ~/spyder_logs
mkdir -p ~/spyder_backups

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \\
    xvfb \\
    x11vnc \\
    xfonts-base \\
    xauth \\
    fonts-dejavu-core \\
    fonts-liberation \\
    libxext6 \\
    libxrender1 \\
    libxtst6 \\
    socat \\
    zenity \\
    openjdk-8-jre \\
    python3-pip \\
    tmux \\
    netcat-openbsd

# Install Python packages
echo "Installing Python packages..."
pip3 install --upgrade \\
    ib_async \\
    psutil \\
    cryptography \\
    pandas \\
    numpy

# Add Spyder configuration to .bashrc
echo "Configuring .bashrc..."
{self.generate_spyder_config()}

echo "✅ Environment setup complete!"
echo "Run 'source ~/.bashrc' to apply changes"
"""
        
        try:
            filepath.write_text(script_content)
            filepath.chmod(0o755)  # Make executable
            self.logger.info(f"✅ Setup script created: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create setup script: {e}")
            return False

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def quick_install():
    """Quick installation of Spyder configuration"""
    manager = BashrcConfigurationManager()
    
    print("📝 Quick Install - Spyder Trading System")
    print("=" * 60)
    
    # Check current status
    if manager.has_spyder_config():
        print("⚠️  Existing configuration detected")
        manager.config.force_update = True
    
    # Install configuration
    if manager.install_configuration():
        print("\n✅ Installation complete!")
        print("\nNext steps:")
        print("1. Run: source ~/.bashrc")
        print("2. Test: spyder_health_check")
        print("3. Start Gateway: spyder_gateway_start")
    else:
        print("\n❌ Installation failed")
        return False
    
    return True

def validate_current():
    """Validate current configuration"""
    manager = BashrcConfigurationManager()
    
    print("🔍 Validating Current Configuration")
    print("=" * 60)
    
    result = manager.validate_configuration()
    
    if result.is_valid:
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration has issues:")
        
        if result.missing_vars:
            print(f"\nMissing variables: {', '.join(result.missing_vars)}")
        
        if result.incorrect_vars:
            print("\nIncorrect variables:")
            for var, issue in result.incorrect_vars.items():
                print(f"  • {var}: {issue}")
        
        if result.missing_aliases:
            print(f"\nMissing aliases: {', '.join(result.missing_aliases)}")
    
    if result.warnings:
        print("\n⚠️  Warnings:")
        for warning in result.warnings:
            print(f"  • {warning}")
    
    return result.is_valid

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Spyder Trading System - Bashrc Configuration Manager"
    )
    
    parser.add_argument(
        "action",
        choices=["install", "validate", "backup", "restore", "migrate", "show", "script"],
        help="Action to perform"
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (no actual changes)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update without confirmation"
    )
    
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create manager
    config = BashrcConfig(
        test_mode=args.test,
        force_update=args.force,
        backup_enabled=not args.no_backup
    )
    
    manager = BashrcConfigurationManager(config)
    
    # Execute action
    if args.action == "install":
        print("🚀 Installing Spyder Configuration")
        print("=" * 60)
        success = manager.install_configuration()
        sys.exit(0 if success else 1)
        
    elif args.action == "validate":
        success = validate_current()
        sys.exit(0 if success else 1)
        
    elif args.action == "backup":
        path = manager.backup_bashrc()
        if path:
            print(f"✅ Backup created: {path}")
            sys.exit(0)
        else:
            print("❌ Backup failed")
            sys.exit(1)
            
    elif args.action == "restore":
        if manager.restore_bashrc():
            print("✅ Restore completed")
            sys.exit(0)
        else:
            print("❌ Restore failed")
            sys.exit(1)
            
    elif args.action == "migrate":
        if manager.migrate_from_1037():
            print("✅ Migration completed")
            sys.exit(0)
        else:
            print("❌ Migration failed")
            sys.exit(1)
            
    elif args.action == "show":
        manager.show_current_config()
        sys.exit(0)
        
    elif args.action == "script":
        if manager.create_setup_script():
            print("✅ Setup script created: setup_spyder_env.sh")
            print("Run: ./setup_spyder_env.sh")
            sys.exit(0)
        else:
            print("❌ Script creation failed")
            sys.exit(1)
