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
    ("SpyderG06_RiskParametersDialog", ["RiskParametersDialog", "show_risk_parameters_dialog"]),
]

# Import each module with error handling
for module_info in modules_to_import:
    module_name = module_info[0]
    items_to_import = module_info[1]
    
    try:
        if module_name == "SpyderG02_GUIEntry":
            # Special handling for the entry point function
            module = __import__(f".{module_name}", globals(), locals(), ["main"], 1)
            gui_main = module.main
            __all__.append("gui_main")
        elif isinstance(items_to_import, list):
            # Handle modules with multiple exports
            module = __import__(f".{module_name}", globals(), locals(), items_to_import, 1)
            for item in items_to_import:
                globals()[item] = getattr(module, item)
                __all__.append(item)
        else:
            # Import single class normally
            module = __import__(f".{module_name}", globals(), locals(), [items_to_import], 1)
            globals()[items_to_import] = getattr(module, items_to_import)
            __all__.append(items_to_import)
        
        print(f"✅ SpyderG_GUI: {module_name} loaded successfully")
    except Exception as e:
        print(f"⚠️  SpyderG_GUI: {module_name} not available: {e}")

print(f"✅ SpyderG_GUI: {len(__all__)} modules loaded successfully")

# Export version
__all__.append("__version__")
