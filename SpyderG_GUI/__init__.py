#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - GUI Package
Graphical User Interface components for the Spyder trading system
"""

__version__ = '2.0.0'
__all__ = []

# Import GUI modules in order
modules_to_import = [
    ("SpyderG01_MainWindow", "SpyderMainWindow"),
    ("SpyderG02_GUIEntry", "gui_main"),
    ("SpyderG03_OptionChainWidget", "OptionChainWidget"),
    ("SpyderG04_ChartWidget", "ChartWidget"),
    ("SpyderG05_TradingDashboard", "SpyderTradingDashboard"),
]

# Import each module with error handling
for module_name, class_name in modules_to_import:
    try:
        if module_name == "SpyderG02_GUIEntry":
            # Special handling for the entry point function
            module = __import__(f".{module_name}", globals(), locals(), ["main"], 1)
            gui_main = module.main
            __all__.append("gui_main")
        else:
            # Import classes normally
            module = __import__(f".{module_name}", globals(), locals(), [class_name], 1)
            globals()[class_name] = getattr(module, class_name)
            __all__.append(class_name)
        print(f"✅ SpyderG_GUI: {module_name} loaded successfully")
    except Exception as e:
        print(f"⚠️  SpyderG_GUI: {module_name} not available: {e}")

print(f"✅ SpyderG_GUI: {len(__all__)} modules loaded successfully")

# Export version
__all__.append("__version__")
