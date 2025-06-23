#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
SpyderB_Broker Package

This package handles all broker interactions, primarily with Interactive Brokers Gateway.
Uses ib-insync library (NO IBAPI dependencies).
"""

# Version
__version__ = '1.5.0'

# Main imports
try:
    from .SpyderB01_SpyderClient import SpyderClient, get_spyder_client
    HAS_SPYDER_CLIENT = True
except ImportError:
    print("WARNING: SpyderClient not available")
    HAS_SPYDER_CLIENT = False

# Type aliases
TickerId = int

# Public API
__all__ = [
    'SpyderClient',
    'get_spyder_client', 
    'TickerId',
]

# Additional exports if available
if HAS_SPYDER_CLIENT:
    __all__.extend(['HAS_SPYDER_CLIENT'])
