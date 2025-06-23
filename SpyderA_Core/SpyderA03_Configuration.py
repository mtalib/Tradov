#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Configuration Manager (Minimal Implementation)
"""

from pathlib import Path
from typing import Dict, Any
import logging

class ConfigManager:
    """Minimal configuration manager."""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self._config = self._load_default_config()
        
        self.logger.info("ConfigManager initialized")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration."""
        return {
            'demo_mode': True,
            'ib': {
                'host': '127.0.0.1',
                'port': 4002,
                'client_id': 1
            },
            'risk': {
                'max_position_size': 1000,
                'max_daily_loss': 500
            },
            'logging': {
                'level': 'INFO'
            }
        }
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self._config.get(key, default)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration."""
        return self._config.copy()
    
    def update(self, key: str, value: Any):
        """Update configuration value."""
        self._config[key] = value

# Factory function
def get_config_manager(config_path: Path = None) -> ConfigManager:
    """Get ConfigManager instance."""
    return ConfigManager(config_path)

__all__ = ['ConfigManager', 'get_config_manager']
