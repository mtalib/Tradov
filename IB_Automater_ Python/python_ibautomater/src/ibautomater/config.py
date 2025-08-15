"""
Configuration classes and enums for IBAutomater
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TradingMode(Enum):
    """Trading mode enumeration"""
    PAPER = "paper"
    LIVE = "live"


class Region(Enum):
    """Regional settings enumeration"""
    US = "us"
    EUROPE = "europe"
    ASIA = "asia"


@dataclass
class IBConfig:
    """Configuration for IBAutomater"""
    
    # Required settings
    ib_directory: str
    ib_version: str
    username: str
    password: str
    trading_mode: TradingMode
    port: int
    
    # Optional settings
    export_logs: bool = False
    auto_restart_time: str = "23:45"
    region: Region = Region.US
    java_heap_size: str = "4096m"
    timeout_seconds: int = 300
    max_login_attempts: int = 3
    two_factor_timeout: int = 180  # 3 minutes
    
    # UI automation settings
    ui_timeout: float = 30.0
    screenshot_interval: float = 1.0
    template_match_threshold: float = 0.8
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self.validate()
    
    def validate(self):
        """Validate configuration parameters"""
        # Validate IB directory exists
        ib_path = Path(self.ib_directory)
        if not ib_path.exists():
            raise ValueError(f"IB directory does not exist: {self.ib_directory}")
        
        # Validate port range
        if not (1024 <= self.port <= 65535):
            raise ValueError(f"Port must be between 1024 and 65535, got: {self.port}")
        
        # Validate timeout values
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        
        if self.two_factor_timeout <= 0:
            raise ValueError("Two factor timeout must be positive")
        
        # Validate credentials
        if not self.username or not self.password:
            raise ValueError("Username and password are required")
    
    @property
    def gateway_executable(self) -> str:
        """Get the path to the IB Gateway executable"""
        import platform
        system = platform.system().lower()
        
        if system == "windows":
            return str(Path(self.ib_directory) / "ibgateway.exe")
        elif system == "darwin":  # macOS
            return str(Path(self.ib_directory) / "IBGateway.app" / "Contents" / "MacOS" / "IBGateway")
        else:  # Linux
            return str(Path(self.ib_directory) / "ibgateway")
    
    @property
    def java_executable(self) -> str:
        """Get the path to the Java executable bundled with IB Gateway"""
        import platform
        system = platform.system().lower()
        
        if system == "windows":
            return str(Path(self.ib_directory) / "jre" / "bin" / "java.exe")
        else:
            return str(Path(self.ib_directory) / "jre" / "bin" / "java")
    
    def get_gateway_args(self) -> list:
        """Get command line arguments for starting IB Gateway"""
        args = [
            self.gateway_executable,
            f"-Xmx{self.java_heap_size}",
            f"-Dport={self.port}",
            f"-Dmode={self.trading_mode.value}",
        ]
        
        if self.export_logs:
            args.append("-Dexport.logs=true")
        
        return args

