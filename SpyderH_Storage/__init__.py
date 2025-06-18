#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderH_Storage
Purpose: Data Persistence

This package provides data persistence functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderH01_DataAccessLayer import DataAccessLayer, get_dal

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "DataAccessLayer",
    "get_dal",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderH_Storage"
__description__ = "Data Persistence Layer"
__version__ = "1.4.0"