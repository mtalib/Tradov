#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU22_ETTimeDisplay.py
Purpose: Simple ET time display for dashboard (top-right time replacement)
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 17:15:00  

Module Description:
    Simple utility to provide properly formatted Eastern Time string for the
    existing dashboard time display (top-right). Replaces local time with
    accurate ET time using SpyderU03's trading hours infrastructure. No design
    changes, just correct time display in the existing location.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime
from typing import Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU03_DateTimeUtils import US_EASTERN

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Simple time format for dashboard
DASHBOARD_TIME_FORMAT = "%H:%M:%S %Z"  # "15:45:23 EDT"
SIMPLE_TIME_FORMAT = "%H:%M:%S"        # "15:45:23" (if no timezone needed)

# Eastern timezone
EASTERN_TZ = pytz.timezone(US_EASTERN)

# ==============================================================================
# MAIN FUNCTIONS
# ==============================================================================
def get_et_time_string(include_timezone: bool = True) -> str:
    """
    Get current Eastern Time as formatted string for dashboard display.
    
    Args:
        include_timezone: Whether to include timezone abbreviation (EDT/EST)
        
    Returns:
        str: Formatted ET time string
    """
    try:
        # Get current Eastern Time
        et_now = datetime.now(EASTERN_TZ)
        
        # Format based on requirement
        if include_timezone:
            return et_now.strftime(DASHBOARD_TIME_FORMAT)  # "15:45:23 EDT"
        else:
            return et_now.strftime(SIMPLE_TIME_FORMAT)     # "15:45:23"
            
    except Exception:
        # Fallback to local time if ET fails
        return datetime.now().strftime(SIMPLE_TIME_FORMAT)

def get_et_time_for_dashboard() -> str:
    """
    Get ET time string specifically formatted for dashboard top-right display.
    
    Returns:
        str: ET time string for dashboard
    """
    return get_et_time_string(include_timezone=True)

def get_current_et_datetime() -> datetime:
    """
    Get current datetime in Eastern timezone.
    
    Returns:
        datetime: Current ET datetime object
    """
    try:
        return datetime.now(EASTERN_TZ)
    except Exception:
        return datetime.now()

# ==============================================================================
# SIMPLE CLASS (Optional - for caching if needed)
# ==============================================================================
class SimpleETDisplay:
    """
    Simple ET time display utility.
    
    Minimal class for getting ET time strings without overhead.
    Only needed if you want to cache the timezone object.
    """
    
    def __init__(self):
        """Initialize with Eastern timezone."""
        self.eastern_tz = EASTERN_TZ
        self.logger = SpyderLogger.get_logger(__name__)
    
    def get_time_string(self, include_tz: bool = True) -> str:
        """Get ET time string."""
        try:
            et_now = datetime.now(self.eastern_tz)
            if include_tz:
                return et_now.strftime(DASHBOARD_TIME_FORMAT)
            else:
                return et_now.strftime(SIMPLE_TIME_FORMAT)
        except Exception as e:
            self.logger.error(f"ET time error: {e}")
            return datetime.now().strftime(SIMPLE_TIME_FORMAT)

# ==============================================================================
# MODULE-LEVEL INSTANCE (if caching needed)
# ==============================================================================
_et_display = None

def get_et_display():
    """Get singleton ET display instance."""
    global _et_display
    if _et_display is None:
        _et_display = SimpleETDisplay()
    return _et_display

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the simple ET time display
    print("SPYDER U22 - Simple ET Time Display Test")
    print("=" * 50)
    
    print(f"ET Time (with TZ): {get_et_time_string(True)}")
    print(f"ET Time (no TZ):   {get_et_time_string(False)}")
    print(f"Dashboard Format:  {get_et_time_for_dashboard()}")
    
    # Test class version
    display = SimpleETDisplay()
    print(f"Class Version:     {display.get_time_string()}")
    
    # Test datetime object
    et_dt = get_current_et_datetime()
    print(f"ET Datetime:       {et_dt}")
    print(f"Is DST:            {bool(et_dt.dst())}")
    
    print("\n✅ Simple ET time display working!")
    print("🕐 Ready to replace dashboard top-right time display")
