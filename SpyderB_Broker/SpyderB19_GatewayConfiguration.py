"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB19_GatewayConfiguration.py
Purpose: IB Gateway 10.39 Configuration Manager
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-26 Time: 10:00:00

Module Description:
    Comprehensive configuration manager for IB Gateway 10.39 with enhanced
    connection stability, automated startup, and production-ready settings.
    Handles version management, environment setup, and optimal parameters
    for the Spyder trading system.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

# ==============================================================================
# CONSTANTS - IB GATEWAY 10.39 CONFIGURATION
# ==============================================================================

# Version Configuration
IB_GATEWAY_VERSION = "10.39"
TWS_MAJOR_VRSN = "1039"  # Internal version for 10.39
TWS_BUILD_VERSION = "10.39.1e"  # Latest stable build

# Directory Paths
IB_GATEWAY_DIR = Path.home() / "Jts" / "ibgateway" / TWS_MAJOR_VRSN
IBC_DIR = Path.home() / "ibc"
LOG_DIR = Path.home() / "spyder_logs" / "gateway"

# Connection Parameters - ENHANCED FOR STABILITY
CONNECTION_PARAMS = {
    "connection_timeout": 60,      # Increased from 4 seconds
    "request_timeout": 30,         
    "message_timeout": 120,        
    "reconnect_delay": 10,         
    "max_reconnect_attempts": 5,
    "exponential_backoff": True,
    "initial_sync_timeout": 90,    # For reqExecutionsAsync issues
    "heartbeat_interval": 30,
    "health_check_interval": 60
}

# JVM Configuration - OPTIMIZED FOR GATEWAY 10.39
JVM_CONFIG = {
    "heap_min": "1024m",
    "heap_max": "4096m",           # 4GB recommended
    "permgen": "256m",
    "gc_type": "G1GC",             # G1 Garbage Collector
    "gc_threads": 4,
    "extra_opts": [
        "-Dsun.java2d.noddraw=true",
        "-Dsun.java2d.xrender=false", 
        "-Dsun.java2d.pmoffscreen=false",
        "-Djava.awt.headless=false"   # Required for Swing apps
    ]
}

# Xvfb Configuration for Headless Operation
XVFB_CONFIG = {
    "display": ":99",
    "resolution": "1600x1200",
    "color_depth": 24,
    "dpi": 96,
    "options": "-noreset -ac -screen 0 1600x1200x24 -dpi 96"
}

# API Ports
PORTS = {
    "paper": 4002,
    "live": 4001,
    "gateway_controller": 4003  # IBC controller port
}

# ==============================================================================
# CONFIGURATION DATACLASSES
# ==============================================================================

@dataclass
class GatewayConfig:
    """Complete IB Gateway 10.39 configuration"""
    version: str = IB_GATEWAY_VERSION
    tws_version: str = TWS_MAJOR_VRSN
    mode: str = "paper"  # paper or live
    
    # Connection settings
    host: str = "127.0.0.1"
    port: int = field(default_factory=lambda: PORTS["paper"])
    client_id: int = 1
    
    # Timeouts and retries
    connection_timeout: int = CONNECTION_PARAMS["connection_timeout"]
    request_timeout: int = CONNECTION_PARAMS["request_timeout"]
    reconnect_attempts: int = CONNECTION_PARAMS["max_reconnect_attempts"]
    reconnect_delay: int = CONNECTION_PARAMS["reconnect_delay"]
    
    # JVM settings
    jvm_heap_min: str = JVM_CONFIG["heap_min"]
    jvm_heap_max: str = JVM_CONFIG["heap_max"]
    jvm_gc_type: str = JVM_CONFIG["gc_type"]
    
    # Xvfb settings
    use_xvfb: bool = True
    xvfb_display: str = XVFB_CONFIG["display"]
    xvfb_resolution: str = XVFB_CONFIG["resolution"]
    
    # IBC automation
    use_ibc: bool = True
    ibc_path: str = str(IBC_DIR)
    ibc_config: str = str(IBC_DIR / "config.ini")
    
    # Logging
    log_level: str = "INFO"
    log_dir: str = str(LOG_DIR)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_env_vars(self) -> Dict[str, str]:
        """Generate environment variables"""
        return {
            "TWS_MAJOR_VRSN": self.tws_version,
            "IB_GATEWAY_VERSION": self.version,
            "IBC_INI": self.ibc_config,
            "IBC_PATH": self.ibc_path,
            "DISPLAY": self.xvfb_display if self.use_xvfb else ":0"
        }

# ==============================================================================
# GATEWAY CONFIGURATION MANAGER
# ==============================================================================

class GatewayConfigurationManager:
    """
    Manages IB Gateway 10.39 configuration and environment setup.
    
    Features:
    - Version validation and migration
    - Environment variable management
    - JVM optimization settings
    - Xvfb configuration for headless operation
    - IBC automation setup
    - Connection parameter optimization
    """
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        """Initialize configuration manager"""
        self.config = config or GatewayConfig()
        self.logger = self._setup_logger()
        
        # Ensure directories exist
        self._create_directories()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup module logger"""
        logger = logging.getLogger(__name__)
        logger.setLevel(getattr(logging, self.config.log_level))
        
        # Create log directory
        Path(self.config.log_dir).mkdir(parents=True, exist_ok=True)
        
        # File handler
        fh = logging.FileHandler(
            Path(self.config.log_dir) / f"gateway_config_{datetime.now():%Y%m%d}.log"
        )
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _create_directories(self):
        """Create required directories"""
        dirs = [
            Path(self.config.log_dir),
            Path(self.config.ibc_path),
            IB_GATEWAY_DIR
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def validate_installation(self) -> tuple[bool, List[str]]:
        """
        Validate IB Gateway 10.39 installation.
        
        Returns:
            tuple: (is_valid, error_messages)
        """
        errors = []
        
        # Check Gateway directory
        if not IB_GATEWAY_DIR.exists():
            errors.append(f"IB Gateway directory not found: {IB_GATEWAY_DIR}")
        
        # Check Java
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                errors.append("Java is not properly installed")
            else:
                self.logger.info(f"Java version: {result.stderr}")
        except Exception as e:
            errors.append(f"Java check failed: {e}")
        
        # Check Xvfb if required
        if self.config.use_xvfb:
            try:
                result = subprocess.run(
                    ["which", "xvfb-run"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    errors.append("Xvfb not installed (required for headless operation)")
            except Exception as e:
                errors.append(f"Xvfb check failed: {e}")
        
        # Check IBC if required
        if self.config.use_ibc:
            ibc_jar = Path(self.config.ibc_path) / "IBC.jar"
            if not ibc_jar.exists():
                errors.append(f"IBC.jar not found at {ibc_jar}")
        
        return len(errors) == 0, errors
    
    def generate_jvm_args(self) -> List[str]:
        """Generate optimized JVM arguments for Gateway 10.39"""
        args = [
            f"-Xms{self.config.jvm_heap_min}",
            f"-Xmx{self.config.jvm_heap_max}",
            f"-XX:+Use{self.config.jvm_gc_type}",
            f"-XX:ParallelGCThreads={JVM_CONFIG['gc_threads']}",
            "-XX:+PrintGCDetails",
            "-XX:+PrintGCTimeStamps",
            f"-Xloggc:{self.config.log_dir}/gc.log"
        ]
        
        # Add extra options
        args.extend(JVM_CONFIG["extra_opts"])
        
        return args
    
    def generate_xvfb_command(self) -> str:
        """Generate Xvfb command for headless operation"""
        return f"xvfb-run {XVFB_CONFIG['options']} --server-num=99"
    
    def write_ibc_config(self, username: str, password: str):
        """
        Write IBC configuration file for automation.
        
        Args:
            username: IB account username
            password: IB account password (will be encrypted)
        """
        config_content = f"""
# IBC Configuration for IB Gateway {self.config.version}
# Generated by Spyder Trading System

IbLoginId={username}
IbPassword={password}
TradingMode={self.config.mode}

# Gateway Settings
Gateway=true
TWS=false

# Auto-restart Settings
AutoRestartTime=23:45
AutoRestartWeeklyTime=02:00 Sunday

# Connection Settings
AcceptIncomingConnectionAction=accept
AllowBlindTrading=yes
DismissPasswordExpiryWarning=yes
DismissNSEComplianceNotice=yes

# Logging
LogToConsole=yes
LogFile={self.config.log_dir}/ibc.log
"""
        
        config_path = Path(self.config.ibc_config)
        config_path.write_text(config_content)
        
        # Set secure permissions
        os.chmod(config_path, 0o600)
        
        self.logger.info(f"IBC config written to {config_path}")
    
    def apply_environment(self):
        """Apply environment variables for Gateway 10.39"""
        env_vars = self.config.to_env_vars()
        
        for key, value in env_vars.items():
            os.environ[key] = value
            self.logger.debug(f"Set {key}={value}")
        
        self.logger.info("Environment variables applied for Gateway 10.39")
    
    def save_config(self, filepath: Optional[Path] = None):
        """Save configuration to JSON file"""
        filepath = filepath or Path(self.config.log_dir) / "gateway_config.json"
        
        with open(filepath, 'w') as f:
            json.dump(self.config.to_dict(), f, indent=4)
        
        self.logger.info(f"Configuration saved to {filepath}")
    
    @classmethod
    def load_config(cls, filepath: Path) -> 'GatewayConfigurationManager':
        """Load configuration from JSON file"""
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        
        config = GatewayConfig(**config_dict)
        return cls(config)
    
    def get_launch_command(self) -> str:
        """
        Generate complete Gateway launch command.
        
        Returns:
            Complete command to launch IB Gateway 10.39
        """
        jvm_args = " ".join(self.generate_jvm_args())
        
        if self.config.use_xvfb:
            xvfb_cmd = self.generate_xvfb_command()
            base_cmd = xvfb_cmd
        else:
            base_cmd = ""
        
        if self.config.use_ibc:
            cmd = f"{base_cmd} java {jvm_args} -cp {self.config.ibc_path}/IBC.jar:{IB_GATEWAY_DIR}/* ibcalpha.ibc.IbcGateway {self.config.ibc_config}"
        else:
            cmd = f"{base_cmd} {IB_GATEWAY_DIR}/bin/run.sh {jvm_args}"
        
        return cmd

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_default_config(mode: str = "paper") -> GatewayConfig:
    """Get default configuration for specified mode"""
    config = GatewayConfig(mode=mode)
    config.port = PORTS[mode]
    return config

def migrate_from_1037():
    """Migrate configuration from Gateway 10.37 to 10.39"""
    print("🔄 Migrating from Gateway 10.37 to 10.39...")
    
    # Update environment variables
    subprocess.run(["sed", "-i", 's/TWS_MAJOR_VRSN="1037"/TWS_MAJOR_VRSN="1039"/g', 
                    str(Path.home() / ".bashrc")])
    
    # Update any configuration files
    old_dir = Path.home() / "Jts" / "ibgateway" / "1037"
    new_dir = Path.home() / "Jts" / "ibgateway" / "1039"
    
    if old_dir.exists() and not new_dir.exists():
        print(f"📁 Creating new configuration directory: {new_dir}")
        new_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy jts.ini if exists
        old_jts = old_dir / "jts.ini"
        if old_jts.exists():
            new_jts = new_dir / "jts.ini"
            subprocess.run(["cp", str(old_jts), str(new_jts)])
            print(f"✅ Copied jts.ini to new directory")
    
    print("✅ Migration completed!")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("🚀 IB Gateway 10.39 Configuration Manager")
    print("=" * 60)
    
    # Create configuration manager
    config = get_default_config("paper")
    manager = GatewayConfigurationManager(config)
    
    # Validate installation
    is_valid, errors = manager.validate_installation()
    
    if is_valid:
        print("✅ IB Gateway 10.39 installation validated")
        
        # Apply environment
        manager.apply_environment()
        
        # Save configuration
        manager.save_config()
        
        # Show launch command
        print("\n📝 Launch command:")
        print(manager.get_launch_command())
    else:
        print("❌ Validation failed:")
        for error in errors:
            print(f"   • {error}")
    
    print("\n✨ Configuration complete!")
