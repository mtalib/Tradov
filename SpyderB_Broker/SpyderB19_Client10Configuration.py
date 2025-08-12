#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB19_Client10Configuration.py
Group: B (Broker/Connection)
Purpose: Configuration for Client 10 (Custom Metrics)
Author: Mohamed Talib
Date Created: 2025-08-12
Last Updated: 2025-08-12 Time: 18:00:00

Description:
    Configuration module for Client 10 which handles custom market metrics.
    Defines settings for GEX, DEX, OGL, DIX, and SWAN calculations including
    update intervals, thresholds, and data source configurations.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import os
from pathlib import Path
from datetime import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False

# ==============================================================================
# ENUMS
# ==============================================================================
class MetricType(Enum):
    """Types of custom metrics"""
    GEX = "Gamma Exposure"
    DEX = "Delta Exposure"
    OGL = "Zero Gamma Level"
    DIX = "Dark Index"
    SWAN = "Black Swan Risk"

class UpdateFrequency(Enum):
    """Update frequency for metrics"""
    REALTIME = 5  # seconds
    FAST = 30
    NORMAL = 60
    SLOW = 300
    DAILY = 86400

class DataSource(Enum):
    """Data sources for metrics calculation"""
    IB_OPTIONS = "ib_options"
    IB_MARKET = "ib_market"
    EXTERNAL_API = "external_api"
    CALCULATION = "calculation"
    SIMULATION = "simulation"

# ==============================================================================
# CONFIGURATION DATACLASSES
# ==============================================================================

@dataclass
class MetricConfig:
    """Configuration for individual metric"""
    name: str
    type: MetricType
    enabled: bool = True
    update_frequency: UpdateFrequency = UpdateFrequency.NORMAL
    data_source: DataSource = DataSource.IB_OPTIONS
    
    # Display settings
    display_unit: str = ""
    decimal_places: int = 2
    color_positive: str = "#00ff41"
    color_negative: str = "#ff1744"
    color_neutral: str = "#ffd700"
    
    # Thresholds
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    
    # Calculation parameters
    calculation_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GEXConfig(MetricConfig):
    """Gamma Exposure specific configuration"""
    def __init__(self):
        super().__init__(
            name="GEX",
            type=MetricType.GEX,
            display_unit="B",
            decimal_places=1,
            warning_threshold=-3.0,  # -3 billion
            critical_threshold=-5.0,  # -5 billion
            calculation_params={
                "spot_range_pct": 0.20,  # Consider strikes within 20% of spot
                "min_open_interest": 100,
                "contract_multiplier": 100,
                "include_weekly": True,
                "include_monthly": True,
                "aggregate_method": "net"  # net or absolute
            }
        )

@dataclass
class DEXConfig(MetricConfig):
    """Delta Exposure specific configuration"""
    def __init__(self):
        super().__init__(
            name="DEX",
            type=MetricType.DEX,
            display_unit="M",
            decimal_places=0,
            warning_threshold=-1500,  # -1500 million
            critical_threshold=-2500,  # -2500 million
            calculation_params={
                "spot_range_pct": 0.15,
                "min_open_interest": 50,
                "contract_multiplier": 100,
                "hedge_assumption": 0.50  # Assume 50% hedged
            }
        )

@dataclass
class OGLConfig(MetricConfig):
    """Zero Gamma Level specific configuration"""
    def __init__(self):
        super().__init__(
            name="OGL",
            type=MetricType.OGL,
            display_unit="",
            decimal_places=2,
            color_neutral="#ff9800",  # Orange for OGL
            calculation_params={
                "interpolation_method": "linear",
                "smoothing_window": 5,
                "confidence_level": 0.95,
                "use_weighted_gamma": True
            }
        )

@dataclass
class DIXConfig(MetricConfig):
    """Dark Index specific configuration"""
    def __init__(self):
        super().__init__(
            name="DIX",
            type=MetricType.DIX,
            display_unit="%",
            decimal_places=1,
            warning_threshold=38.0,  # Below 38%
            critical_threshold=35.0,  # Below 35%
            data_source=DataSource.EXTERNAL_API,
            calculation_params={
                "data_provider": "squeeze_metrics",
                "lookback_days": 1,
                "smoothing": "ema",
                "smoothing_period": 5
            }
        )

@dataclass
class SWANConfig(MetricConfig):
    """Black Swan Risk specific configuration"""
    def __init__(self):
        super().__init__(
            name="SWAN",
            type=MetricType.SWAN,
            display_unit="",
            decimal_places=2,
            warning_threshold=2.5,  # Risk level 2.5
            critical_threshold=3.5,  # Risk level 3.5
            calculation_params={
                "vix_weight": 0.35,
                "skew_weight": 0.30,
                "pcr_weight": 0.20,
                "term_structure_weight": 0.15,
                "scale_min": 1.0,
                "scale_max": 5.0,
                "use_percentile_scaling": True
            }
        )

@dataclass
class Client10Configuration:
    """Complete configuration for Client 10 (Custom Metrics)"""
    
    # Client identification
    client_id: int = 10
    client_name: str = "Custom Metrics"
    client_purpose: str = "GEX/DEX/OGL/DIX/SWAN"
    
    # Connection settings
    enabled: bool = True
    auto_connect: bool = True
    reconnect_attempts: int = 3
    reconnect_delay: int = 5  # seconds
    
    # Port configuration
    paper_port: int = 4002
    live_port: int = 4001
    use_paper: bool = True
    
    # Update settings
    global_update_interval: int = 60  # seconds
    batch_requests: bool = True
    max_concurrent_requests: int = 5
    
    # Market hours
    update_during_market_hours: bool = True
    update_during_extended_hours: bool = True
    update_on_weekends: bool = False
    
    # Metric configurations
    gex_config: GEXConfig = field(default_factory=GEXConfig)
    dex_config: DEXConfig = field(default_factory=DEXConfig)
    ogl_config: OGLConfig = field(default_factory=OGLConfig)
    dix_config: DIXConfig = field(default_factory=DIXConfig)
    swan_config: SWANConfig = field(default_factory=SWANConfig)
    
    # Data storage
    store_history: bool = True
    history_retention_days: int = 30
    database_table: str = "custom_metrics"
    
    # Alerting
    enable_alerts: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["log", "gui"])
    
    # Performance
    cache_enabled: bool = True
    cache_ttl: int = 30  # seconds
    
    # Simulation mode
    enable_simulation: bool = True  # Falls back to simulation if IB unavailable
    simulation_variance: float = 0.1  # 10% variance in simulated data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "client_purpose": self.client_purpose,
            "enabled": self.enabled,
            "auto_connect": self.auto_connect,
            "reconnect_attempts": self.reconnect_attempts,
            "reconnect_delay": self.reconnect_delay,
            "paper_port": self.paper_port,
            "live_port": self.live_port,
            "use_paper": self.use_paper,
            "global_update_interval": self.global_update_interval,
            "batch_requests": self.batch_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "update_during_market_hours": self.update_during_market_hours,
            "update_during_extended_hours": self.update_during_extended_hours,
            "update_on_weekends": self.update_on_weekends,
            "metrics": {
                "GEX": asdict(self.gex_config),
                "DEX": asdict(self.dex_config),
                "OGL": asdict(self.ogl_config),
                "DIX": asdict(self.dix_config),
                "SWAN": asdict(self.swan_config)
            },
            "store_history": self.store_history,
            "history_retention_days": self.history_retention_days,
            "database_table": self.database_table,
            "enable_alerts": self.enable_alerts,
            "alert_channels": self.alert_channels,
            "cache_enabled": self.cache_enabled,
            "cache_ttl": self.cache_ttl,
            "enable_simulation": self.enable_simulation,
            "simulation_variance": self.simulation_variance
        }
    
    def save(self, filepath: Optional[Path] = None):
        """Save configuration to file"""
        if filepath is None:
            filepath = Path("config/client10_config.json")
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=4, default=str)
    
    @classmethod
    def load(cls, filepath: Optional[Path] = None) -> 'Client10Configuration':
        """Load configuration from file"""
        if filepath is None:
            filepath = Path("config/client10_config.json")
        
        if not filepath.exists():
            # Return default configuration
            return cls()
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Create configuration object
        config = cls()
        
        # Update with loaded data
        for key, value in data.items():
            if hasattr(config, key) and key != "metrics":
                setattr(config, key, value)
        
        return config

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

def validate_config(config: Client10Configuration) -> bool:
    """
    Validate Client 10 configuration
    
    Args:
        config: Configuration to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check client ID
        if config.client_id != 10:
            return False
        
        # Check port configuration
        if config.paper_port == config.live_port:
            return False
        
        # Check update interval
        if config.global_update_interval < 5:
            return False
        
        # Check metric configurations
        metrics = [
            config.gex_config,
            config.dex_config,
            config.ogl_config,
            config.dix_config,
            config.swan_config
        ]
        
        for metric in metrics:
            if not metric.name or not metric.type:
                return False
        
        return True
        
    except Exception:
        return False

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_default_config() -> Client10Configuration:
    """Create default Client 10 configuration"""
    return Client10Configuration()

def create_production_config() -> Client10Configuration:
    """Create production Client 10 configuration"""
    config = Client10Configuration()
    
    # Production settings
    config.use_paper = False
    config.enable_simulation = False
    config.global_update_interval = 30  # Faster updates in production
    config.cache_ttl = 15
    config.reconnect_attempts = 5
    
    # Enable all metrics
    config.gex_config.enabled = True
    config.dex_config.enabled = True
    config.ogl_config.enabled = True
    config.dix_config.enabled = True
    config.swan_config.enabled = True
    
    return config

def create_test_config() -> Client10Configuration:
    """Create test Client 10 configuration"""
    config = Client10Configuration()
    
    # Test settings
    config.use_paper = True
    config.enable_simulation = True
    config.global_update_interval = 5  # Fast updates for testing
    config.store_history = False
    config.enable_alerts = False
    
    return config

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'Client10Configuration',
    'MetricType',
    'UpdateFrequency',
    'DataSource',
    'MetricConfig',
    'GEXConfig',
    'DEXConfig',
    'OGLConfig',
    'DIXConfig',
    'SWANConfig',
    'validate_config',
    'create_default_config',
    'create_production_config',
    'create_test_config'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test configuration
    config = create_default_config()
    
    print("Client 10 Configuration Test")
    print("=" * 50)
    print(f"Client ID: {config.client_id}")
    print(f"Client Name: {config.client_name}")
    print(f"Client Purpose: {config.client_purpose}")
    print(f"Enabled: {config.enabled}")
    print(f"Port: {config.paper_port if config.use_paper else config.live_port}")
    print()
    print("Metrics Configuration:")
    print(f"  GEX: {config.gex_config.enabled} (Update: {config.gex_config.update_frequency.value}s)")
    print(f"  DEX: {config.dex_config.enabled} (Update: {config.dex_config.update_frequency.value}s)")
    print(f"  OGL: {config.ogl_config.enabled} (Update: {config.ogl_config.update_frequency.value}s)")
    print(f"  DIX: {config.dix_config.enabled} (Update: {config.dix_config.update_frequency.value}s)")
    print(f"  SWAN: {config.swan_config.enabled} (Update: {config.swan_config.update_frequency.value}s)")
    print()
    
    # Validate
    if validate_config(config):
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration is invalid")
    
    # Save and load test
    config.save(Path("test_client10_config.json"))
    loaded_config = Client10Configuration.load(Path("test_client10_config.json"))
    
    if loaded_config.client_id == config.client_id:
        print("✅ Save/Load test passed")
    
    # Clean up test file
    import os
    if os.path.exists("test_client10_config.json"):
        os.remove("test_client10_config.json")
