#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick fix to add missing factory functions to existing modules.

This script adds the missing factory functions that the __init__.py is expecting:
- create_contract_builder in SpyderB06_ContractBuilder.py
- create_market_data_manager in SpyderB07_MarketDataManager.py  
- create_gateway_automation in SpyderB12_GatewayAutomation.py

These are simple alias functions that point to existing singleton getters.
"""

# ==============================================================================
# ADDITIONS FOR SpyderB06_ContractBuilder.py
# ==============================================================================

ContractBuilder_Addition = '''
# ==============================================================================
# FACTORY FUNCTIONS - ADDED FOR __init__.py COMPATIBILITY
# ==============================================================================

def create_contract_builder(cache_size: int = DEFAULT_CACHE_SIZE) -> ContractBuilder:
    """
    Factory function to create ContractBuilder instance.
    
    Args:
        cache_size: Maximum number of contracts to cache
        
    Returns:
        ContractBuilder: New or existing ContractBuilder instance
    """
    return get_contract_builder()

# Alias for compatibility
def get_builder() -> ContractBuilder:
    """Get ContractBuilder instance (alias for get_contract_builder)."""
    return get_contract_builder()
'''

# ==============================================================================
# ADDITIONS FOR SpyderB07_MarketDataManager.py  
# ==============================================================================

MarketDataManager_Addition = '''
# ==============================================================================
# FACTORY FUNCTIONS - ADDED FOR __init__.py COMPATIBILITY
# ==============================================================================

def create_market_data_manager(config: Optional[MarketDataConfig] = None) -> MarketDataManager:
    """
    Factory function to create MarketDataManager instance.
    
    Args:
        config: Optional market data configuration
        
    Returns:
        MarketDataManager: New or existing MarketDataManager instance
    """
    return get_market_data_manager(config)

# Alias for compatibility
def get_mdm() -> MarketDataManager:
    """Get MarketDataManager instance (alias)."""
    return get_market_data_manager()
'''

# ==============================================================================
# ADDITIONS FOR SpyderB12_GatewayAutomation.py
# ==============================================================================

GatewayAutomation_Addition = '''
# ==============================================================================
# FACTORY FUNCTIONS - ADDED FOR __init__.py COMPATIBILITY  
# ==============================================================================

def create_gateway_automation(config: Optional[GatewayConfig] = None) -> GatewayAutomation:
    """
    Factory function to create GatewayAutomation instance.
    
    Args:
        config: Optional gateway configuration
        
    Returns:
        GatewayAutomation: New or existing GatewayAutomation instance
    """
    return get_gateway_automation(config)

# Alias for compatibility
def get_automation() -> GatewayAutomation:
    """Get GatewayAutomation instance (alias)."""
    return get_gateway_automation()
'''

# ==============================================================================
# INSTRUCTIONS FOR ADDING THESE TO YOUR MODULES
# ==============================================================================

print("INSTRUCTIONS FOR FIXING MISSING FACTORY FUNCTIONS")
print("=" * 60)
print()
print("Add these functions to the END of your existing modules:")
print()
print("1. ADD TO SpyderB06_ContractBuilder.py:")
print("-" * 40)
print(ContractBuilder_Addition)
print()
print("2. ADD TO SpyderB07_MarketDataManager.py:")  
print("-" * 40)
print(MarketDataManager_Addition)
print()
print("3. ADD TO SpyderB12_GatewayAutomation.py:")
print("-" * 40)
print(GatewayAutomation_Addition)
print()
print("THESE ARE SIMPLE ADDITIONS - just copy and paste to the end of each file.")
print("They create the factory functions that __init__.py expects to import.")
