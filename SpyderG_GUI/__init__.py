#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - GUI Package (Minimal - No Crashes)
"""

__version__ = '1.4.0'
__all__ = []

# Only import the main window (which works)
try:
    from .SpyderG01_MainWindow import SpyderMainWindow
    __all__.extend(["SpyderMainWindow"])
    print("✅ SpyderG_GUI: MainWindow loaded successfully")
except Exception as e:
    print(f"Warning: SpyderG01_MainWindow not available: {e}")

# Skip all other GUI modules that have syntax errors
print(f"✅ SpyderG_GUI: {len(__all__)} modules loaded (others skipped due to syntax issues)")
