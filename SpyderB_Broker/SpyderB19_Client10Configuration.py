#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System
================================================================================
Module: SpyderB19_Client10Configuration.py
Group: B (Broker)
Purpose: Configuration updates to include Client 10 (Custom Metrics)
Author: Mohamed Talib
Date Created: 2025-01-15
Last Updated: 2025-01-15 Time: 11:00:00

Description:
    This module provides the configuration updates and patches needed to formally
    include Client 10 as the Custom Metrics Client in the Spyder system. It 
    extends the existing gateway configuration and multi-client data manager to
    recognize and properly manage Client 10 for custom metric calculations
    (GEX, DEX, OGL, DIX, SWAN).

Key Features:
    - Extends client allocation from 1-9 to 1-10
    - Configures Client 10 for custom metrics calculation
    - Updates multi-client manager to recognize Client 10
    - Provides migration utilities for existing configurations
    - Includes validation and health check extensions

Integration Points:
    - Extends SpyderB13_GatewayConfig with Client 10 settings
    - Updates SpyderB08_MultiClientDataManager client allocation
    - Integrates with SpyderB14_MultiClientWatchdog for monitoring
    - Configures SpyderB15_PrometheusMetrics for Client 10 metrics
    
    
    
    
    
    Module Header (line 7):

Change: Module: SpyderB20_Client10Configuration.py
To: Module: SpyderB19_Client10Configuration.py


Logger Names (lines 48, 196, 280):

Change: SpyderB20.Config
To: SpyderB19.Config
Change: SpyderB20.Manager
To: SpyderB19.Manager


Main Execution Print (line 513):

Change: print("🚀 SPYDER B20 - Client 10 Configuration")
To: print("🚀 SPYDER B19 - Client 10 Configuration")
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum, auto

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderB_Broker.SpyderB13_GatewayConfig import (
        GatewayConfig, ClientConfig, ClientPurpose, TradingMode
    )
    from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
        MultiClientDataManager, ClientInfo
    )
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    print("⚠️ Some modules not available, using standalone definitions")

# ==============================================================================
# CONSTANTS
# ==============================================================================
CLIENT_10_ID = 10
CLIENT_10_PURPOSE = "CUSTOM_METRICS"
CLIENT_10_DESCRIPTION = "Custom Metrics Calculation (GEX, DEX, OGL, DIX, SWAN)"

# Update ranges to include Client 10
MIN_CLIENT_ID = 1
MAX_CLIENT_ID = 10
TOTAL_CLIENTS = 10

# ==============================================================================
# EXTENDED ENUMS
# ==============================================================================
class ExtendedClientPurpose(Enum):
    """Extended client purposes including Client 10"""
    ADMINISTRATIVE = "Administrative Operations"
    ORDER_EXECUTION = "Order Execution - HIGHEST PRIORITY"
    CORE_DATA = "Core Market Data"
    SPY_OPTIONS = "SPY Options Chains"
    VOLATILITY = "Volatility Indicators"
    MARKET_INTERNALS = "Market Internals"
    MAJOR_INDICES = "Major Index ETFs"
    EXTENDED_ASSETS = "Extended Market Data"
    SECTOR_ETFS = "Sector ETFs"
    CUSTOM_METRICS = "Custom Metrics Calculation"  # NEW: Client 10

# ==============================================================================
# CLIENT 10 CONFIGURATION
# ==============================================================================
@dataclass
class Client10Config:
    """Configuration specifically for Client 10 (Custom Metrics)"""
    client_id: int = 10
    purpose: str = "CUSTOM_METRICS"
    metrics: List[str] = field(default_factory=lambda: ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN'])
    update_frequencies: Dict[str, float] = field(default_factory=lambda: {
        'GEX': 5.0,
        'DEX': 5.0,
        'OGL': 10.0,
        'DIX': 30.0,
        'SWAN': 60.0
    })
    description: str = "Custom Metrics Calculation Engine"
    priority: str = "HIGH"
    enabled: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 300  # seconds
    
    def to_client_config(self) -> 'ClientConfig':
        """Convert to standard ClientConfig format"""
        if MODULES_AVAILABLE:
            return ClientConfig(
                client_id=self.client_id,
                purpose=ClientPurpose.ADMINISTRATIVE,  # Placeholder, will be extended
                symbols=[],  # No direct market data symbols
                frequency=0.0,  # Variable based on metric
                description=self.description,
                priority=self.priority,
                update_interval=None,
                rate_limit=10  # Lower rate limit as it doesn't need market data
            )
        else:
            return {
                'client_id': self.client_id,
                'purpose': self.purpose,
                'symbols': [],
                'frequency': 0.0,
                'description': self.description,
                'priority': self.priority
            }

# ==============================================================================
# EXTENDED GATEWAY CONFIGURATION
# ==============================================================================
class ExtendedGatewayConfig:
    """
    Extended Gateway Configuration including Client 10.
    
    This class extends the base GatewayConfig to include Client 10
    for custom metrics calculation.
    """
    
    def __init__(self, base_config: Optional['GatewayConfig'] = None):
        """
        Initialize extended configuration.
        
        Args:
            base_config: Optional base GatewayConfig to extend
        """
        self.base_config = base_config
        self.client_10_config = Client10Config()
        
        # Logging
        if MODULES_AVAILABLE:
            self.logger = SpyderLogger.get_logger('SpyderB19.Config')
        else:
            self.logger = logging.getLogger('SpyderB19.Config')
        
        self.logger.info("Extended Gateway Configuration initialized with Client 10")
    
    def get_all_client_configs(self) -> Dict[int, Any]:
        """
        Get all client configurations including Client 10.
        
        Returns:
            Dictionary mapping client_id to configuration
        """
        configs = {}
        
        # Get base configs (1-9)
        if self.base_config and MODULES_AVAILABLE:
            from SpyderB_Broker.SpyderB13_GatewayConfig import get_client_allocation
            configs = get_client_allocation()
        else:
            # Fallback configuration for clients 1-9
            configs = self._get_default_configs_1_to_9()
        
        # Add Client 10
        configs[10] = self.client_10_config.to_client_config()
        
        return configs
    
    def _get_default_configs_1_to_9(self) -> Dict[int, Dict]:
        """Get default configurations for clients 1-9 (fallback)"""
        return {
            1: {'client_id': 1, 'purpose': 'ADMINISTRATIVE', 'symbols': [], 'priority': 'CRITICAL'},
            2: {'client_id': 2, 'purpose': 'ORDER_EXECUTION', 'symbols': [], 'priority': 'CRITICAL'},
            3: {'client_id': 3, 'purpose': 'CORE_DATA', 'symbols': ['SPY', 'SPX', '/ES', 'VIX'], 'priority': 'CRITICAL'},
            4: {'client_id': 4, 'purpose': 'SPY_OPTIONS', 'symbols': ['SPY_0DTE', 'SPY_1DTE'], 'priority': 'CRITICAL'},
            5: {'client_id': 5, 'purpose': 'VOLATILITY', 'symbols': ['VIX9D', 'VXV', 'VXMT'], 'priority': 'HIGH'},
            6: {'client_id': 6, 'purpose': 'MARKET_INTERNALS', 'symbols': ['$TRIN', '$ADD'], 'priority': 'HIGH'},
            7: {'client_id': 7, 'purpose': 'MAJOR_INDICES', 'symbols': ['DIA', 'QQQ', 'IWM'], 'priority': 'HIGH'},
            8: {'client_id': 8, 'purpose': 'EXTENDED_ASSETS', 'symbols': ['TLT', 'LQD', 'DXY'], 'priority': 'MEDIUM'},
            9: {'client_id': 9, 'purpose': 'SECTOR_ETFS', 'symbols': ['XLF', 'XLK', 'XLE'], 'priority': 'LOW'}
        }
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the extended configuration.
        
        Returns:
            Validation results dictionary
        """
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'client_count': 10
        }
        
        # Check Client 10 configuration
        if not self.client_10_config.enabled:
            results['warnings'].append("Client 10 is disabled")
        
        # Validate metrics configuration
        for metric in self.client_10_config.metrics:
            if metric not in self.client_10_config.update_frequencies:
                results['errors'].append(f"Missing update frequency for metric: {metric}")
                results['is_valid'] = False
        
        # Check for conflicts
        all_configs = self.get_all_client_configs()
        if len(all_configs) != 10:
            results['errors'].append(f"Expected 10 clients, found {len(all_configs)}")
            results['is_valid'] = False
        
        return results
    
    def save_extended_config(self, filepath: Path):
        """
        Save extended configuration to file.
        
        Args:
            filepath: Path to save configuration
        """
        config_dict = {
            'version': '2.0',  # Updated version for Client 10
            'updated': datetime.now().isoformat(),
            'total_clients': 10,
            'client_10': {
                'client_id': self.client_10_config.client_id,
                'purpose': self.client_10_config.purpose,
                'metrics': self.client_10_config.metrics,
                'update_frequencies': self.client_10_config.update_frequencies,
                'description': self.client_10_config.description,
                'priority': self.client_10_config.priority,
                'enabled': self.client_10_config.enabled,
                'cache_enabled': self.client_10_config.cache_enabled,
                'cache_ttl': self.client_10_config.cache_ttl
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        self.logger.info(f"Extended configuration saved to {filepath}")
    
    @classmethod
    def load_extended_config(cls, filepath: Path) -> 'ExtendedGatewayConfig':
        """
        Load extended configuration from file.
        
        Args:
            filepath: Path to configuration file
            
        Returns:
            ExtendedGatewayConfig instance
        """
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        
        extended_config = cls()
        
        if 'client_10' in config_dict:
            c10 = config_dict['client_10']
            extended_config.client_10_config = Client10Config(
                client_id=c10.get('client_id', 10),
                purpose=c10.get('purpose', 'CUSTOM_METRICS'),
                metrics=c10.get('metrics', ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']),
                update_frequencies=c10.get('update_frequencies', {}),
                description=c10.get('description', 'Custom Metrics Calculation Engine'),
                priority=c10.get('priority', 'HIGH'),
                enabled=c10.get('enabled', True),
                cache_enabled=c10.get('cache_enabled', True),
                cache_ttl=c10.get('cache_ttl', 300)
            )
        
        return extended_config

# ==============================================================================
# MULTI-CLIENT MANAGER EXTENSION
# ==============================================================================
class ExtendedMultiClientManager:
    """
    Extension for MultiClientDataManager to include Client 10.
    
    This class provides methods to extend the existing MultiClientDataManager
    to recognize and manage Client 10 for custom metrics.
    """
    
    def __init__(self, base_manager: Optional['MultiClientDataManager'] = None):
        """
        Initialize the extended manager.
        
        Args:
            base_manager: Optional base MultiClientDataManager instance
        """
        self.base_manager = base_manager
        self.client_10_info = None
        
        # Logging
        if MODULES_AVAILABLE:
            self.logger = SpyderLogger.get_logger('SpyderB19.Manager')
        else:
            self.logger = logging.getLogger('SpyderB19.Manager')
    
    def add_client_10(self, config: Client10Config):
        """
        Add Client 10 to the multi-client manager.
        
        Args:
            config: Client 10 configuration
        """
        if self.base_manager and MODULES_AVAILABLE:
            # Create ClientInfo for Client 10
            self.client_10_info = ClientInfo(
                client_id=10,
                purpose=ExtendedClientPurpose.CUSTOM_METRICS,
                symbols=[],  # No direct market data symbols
                update_frequency=0.0,  # Variable based on metric
                is_connected=False,
                last_update=None,
                message_count=0,
                error_count=0
            )
            
            # Add to manager's clients dictionary
            self.base_manager.clients[10] = self.client_10_info
            
            # Update client configs
            self.base_manager.client_configs[10] = {
                'purpose': ExtendedClientPurpose.CUSTOM_METRICS,
                'symbols': [],
                'frequency': 0.0,
                'description': config.description,
                'priority': config.priority
            }
            
            self.logger.info("✅ Client 10 added to MultiClientDataManager")
        else:
            self.logger.warning("Base manager not available, Client 10 not added")
    
    def get_client_10_status(self) -> Dict[str, Any]:
        """
        Get status for Client 10.
        
        Returns:
            Status dictionary
        """
        if self.client_10_info:
            return {
                'client_id': 10,
                'purpose': 'CUSTOM_METRICS',
                'is_connected': self.client_10_info.is_connected,
                'message_count': self.client_10_info.message_count,
                'error_count': self.client_10_info.error_count,
                'last_update': self.client_10_info.last_update
            }
        return {
            'client_id': 10,
            'purpose': 'CUSTOM_METRICS',
            'is_connected': False,
            'status': 'Not initialized'
        }
    
    def update_allocation_summary(self) -> str:
        """
        Get updated allocation summary including Client 10.
        
        Returns:
            Formatted allocation summary string
        """
        summary = []
        summary.append("=" * 80)
        summary.append("📊 UPDATED CLIENT ALLOCATION WITH CUSTOM METRICS (1-10)")
        summary.append("=" * 80)
        summary.append("")
        summary.append("🏆 COMPLETE ALLOCATION:")
        
        allocation = [
            (1, "ADMINISTRATIVE", "SYSTEM - Account & control"),
            (2, "ORDER EXECUTION", "CRITICAL - Fastest trading execution"),
            (3, "CORE DATA", "CRITICAL - SPY, VIX real-time (1s)"),
            (4, "SPY OPTIONS", "CRITICAL - 0DTE/1DTE options (1s)"),
            (5, "VOLATILITY", "HIGH - Volatility surface (5s)"),
            (6, "MARKET INTERNALS", "HIGH - Market breadth (5s)"),
            (7, "MAJOR INDICES", "HIGH - DIA/QQQ/IWM (5s)"),
            (8, "EXTENDED ASSETS", "MEDIUM - Bonds/FX/Commodities (15s)"),
            (9, "SECTOR ETFS", "LOW - Sector rotation (30s)"),
            (10, "CUSTOM METRICS", "HIGH - GEX/DEX/OGL/DIX/SWAN calculations")
        ]
        
        for client_id, name, description in allocation:
            if client_id == 10:
                summary.append(f"🔮 Client {client_id}: {name} - {description}")
                summary.append(f"   📈 Metrics: GEX, DEX, OGL, DIX, SWAN")
                summary.append(f"   🧮 Purpose: Complex derivative calculations")
                summary.append(f"   ⚡ Updates: Variable frequency per metric")
            else:
                summary.append(f"📊 Client {client_id}: {name} - {description}")
        
        summary.append("")
        summary.append("🎯 KEY BENEFITS WITH CLIENT 10:")
        summary.append("   • Isolated custom calculations don't impact data feeds")
        summary.append("   • Independent update cycles optimized per metric")
        summary.append("   • Dedicated resources for complex computations")
        summary.append("   • Clean separation between raw data and analytics")
        summary.append("=" * 80)
        
        return "\n".join(summary)

# ==============================================================================
# CONFIGURATION MIGRATION UTILITIES
# ==============================================================================
class ConfigurationMigrator:
    """Utilities for migrating existing configurations to include Client 10"""
    
    @staticmethod
    def migrate_gateway_config(old_config_path: Path, new_config_path: Path):
        """
        Migrate existing gateway configuration to include Client 10.
        
        Args:
            old_config_path: Path to existing configuration
            new_config_path: Path to save migrated configuration
        """
        logger = logging.getLogger('ConfigMigrator')
        
        try:
            # Load existing configuration
            with open(old_config_path, 'r') as f:
                old_config = json.load(f)
            
            # Add Client 10 configuration
            old_config['client_10'] = {
                'client_id': 10,
                'purpose': 'CUSTOM_METRICS',
                'metrics': ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN'],
                'update_frequencies': {
                    'GEX': 5.0,
                    'DEX': 5.0,
                    'OGL': 10.0,
                    'DIX': 30.0,
                    'SWAN': 60.0
                },
                'description': 'Custom Metrics Calculation Engine',
                'priority': 'HIGH',
                'enabled': True,
                'cache_enabled': True,
                'cache_ttl': 300
            }
            
            # Update version and metadata
            old_config['version'] = '2.0'
            old_config['total_clients'] = 10
            old_config['migrated'] = datetime.now().isoformat()
            
            # Save migrated configuration
            with open(new_config_path, 'w') as f:
                json.dump(old_config, f, indent=2)
            
            logger.info(f"✅ Configuration migrated successfully to {new_config_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False
    
    @staticmethod
    def validate_migration(config_path: Path) -> bool:
        """
        Validate that a configuration includes Client 10.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Check for Client 10
            if 'client_10' not in config:
                return False
            
            # Validate Client 10 structure
            c10 = config['client_10']
            required_fields = ['client_id', 'purpose', 'metrics', 'update_frequencies']
            
            for field in required_fields:
                if field not in c10:
                    return False
            
            # Check client ID is correct
            if c10['client_id'] != 10:
                return False
            
            return True
            
        except Exception:
            return False

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_extended_config(base_config: Optional['GatewayConfig'] = None) -> ExtendedGatewayConfig:
    """
    Create extended gateway configuration with Client 10.
    
    Args:
        base_config: Optional base configuration
        
    Returns:
        ExtendedGatewayConfig instance
    """
    return ExtendedGatewayConfig(base_config)

def extend_multi_client_manager(manager: Optional['MultiClientDataManager'] = None) -> ExtendedMultiClientManager:
    """
    Extend multi-client manager with Client 10 support.
    
    Args:
        manager: Optional base manager
        
    Returns:
        ExtendedMultiClientManager instance
    """
    extended = ExtendedMultiClientManager(manager)
    config = Client10Config()
    extended.add_client_10(config)
    return extended

def get_complete_client_allocation() -> Dict[int, Dict[str, Any]]:
    """
    Get complete client allocation including Client 10.
    
    Returns:
        Dictionary mapping all client IDs (1-10) to configurations
    """
    extended_config = create_extended_config()
    return extended_config.get_all_client_configs()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution for testing and demonstration."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("🚀 SPYDER B19 - Client 10 Configuration")
    print("=" * 80)
    
    # Create extended configuration
    extended_config = create_extended_config()
    
    # Validate configuration
    validation = extended_config.validate_configuration()
    print(f"\n✅ Configuration Validation:")
    print(f"   Valid: {validation['is_valid']}")
    print(f"   Client Count: {validation['client_count']}")
    if validation['warnings']:
        print(f"   Warnings: {validation['warnings']}")
    
    # Get all client configs
    all_configs = extended_config.get_all_client_configs()
    print(f"\n📊 All Client Configurations:")
    for client_id, config in all_configs.items():
        if isinstance(config, dict):
            purpose = config.get('purpose', 'Unknown')
            priority = config.get('priority', 'Unknown')
        else:
            purpose = config.purpose.value if hasattr(config.purpose, 'value') else str(config.purpose)
            priority = config.priority
        print(f"   Client {client_id}: {purpose} (Priority: {priority})")
    
    # Display Client 10 specific configuration
    print(f"\n🔮 Client 10 Specific Configuration:")
    c10 = extended_config.client_10_config
    print(f"   Purpose: {c10.purpose}")
    print(f"   Metrics: {', '.join(c10.metrics)}")
    print(f"   Update Frequencies:")
    for metric, freq in c10.update_frequencies.items():
        print(f"      {metric}: {freq}s")
    print(f"   Cache Enabled: {c10.cache_enabled}")
    print(f"   Cache TTL: {c10.cache_ttl}s")
    
    # Create extended manager
    extended_manager = extend_multi_client_manager()
    
    # Display allocation summary
    print(f"\n{extended_manager.update_allocation_summary()}")
    
    # Test configuration save/load
    test_path = Path("/tmp/spyder_config_v2.json")
    extended_config.save_extended_config(test_path)
    print(f"\n💾 Configuration saved to {test_path}")
    
    # Test migration validation
    is_valid = ConfigurationMigrator.validate_migration(test_path)
    print(f"✅ Migration validation: {'Passed' if is_valid else 'Failed'}")
    
    # Get Client 10 status
    c10_status = extended_manager.get_client_10_status()
    print(f"\n📊 Client 10 Status:")
    for key, value in c10_status.items():
        print(f"   {key}: {value}")
    
    print(f"\n✅ Client 10 configuration completed successfully!")
    print(f"🎯 Ready for integration with Custom Metrics Client")

if __name__ == "__main__":
    main()
