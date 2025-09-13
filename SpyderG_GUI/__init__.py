#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - GUI Package
Graphical User Interface components for the Spyder trading system
"""

__version__ = '2.1.0'
__all__ = []

# Import GUI modules in order
modules_to_import = [
    ("SpyderG01_MainWindow", "SpyderMainWindow"),
    ("SpyderG02_GUIEntry", "gui_main"),
    ("SpyderG03_OptionChainWidget", "OptionChainWidget"),
    ("SpyderG04_ChartWidget", "ChartWidget"),
    ("SpyderG05_TradingDashboard", "SpyderTradingDashboard"),
    ("SpyderG06_ClientMonitorPanel", "ClientMonitorPanel"),
    ("SpyderG07_PrometheusMetricsDisplay", "PrometheusMetricsDisplay"),
    ("SpyderG08_DashboardDataBridge", "DashboardDataBridge"),
    ("SpyderG09_RiskParametersDialog", ["RiskParametersDialog", "show_risk_parameters_dialog"]),
    ("SpyderG10_CustomMetricsIntegration", "CustomMetricsIntegration"),
    ("SpyderG11_SkewMonitorDialog", "SkewMonitorDialog"),
    ("SpyderG12_SignalInfoDialog", "SignalInfoDialog"),
    ("SpyderG13_EnhancedWidgets", [
        "SpyderStrikeRangeSlider", 
        "SpyderTradingInput", 
        "SpyderSearchableCombo", 
        "SpyderCollapsibleGroup", 
        "SpyderTradingTooltip", 
        "SpyderWidgetFactory"
    ])
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
                try:
                    globals()[item] = getattr(module, item)
                    __all__.append(item)
                except AttributeError:
                    print(f"⚠️  SpyderG_GUI: {item} not found in {module_name}")
        else:
            # Import single class normally
            module = __import__(f".{module_name}", globals(), locals(), [items_to_import], 1)
            globals()[items_to_import] = getattr(module, items_to_import)
            __all__.append(items_to_import)
        
        print(f"✅ SpyderG_GUI: {module_name} loaded successfully")
    except Exception as e:
        print(f"⚠️  SpyderG_GUI: {module_name} not available: {e}")

print(f"✅ SpyderG_GUI: {len(__all__)} components loaded successfully")

# Export version
__all__.append("__version__")

# Convenience imports for enhanced widgets
try:
    from .SpyderG13_EnhancedWidgets import SpyderWidgetFactory
    
    # Create convenience functions for widget creation
    def create_strike_range_slider(min_strike=400.0, max_strike=500.0):
        """Create a strike range slider widget."""
        return SpyderWidgetFactory.create_strike_range_slider(min_strike, max_strike)
    
    def create_trading_input(input_type="price", label=""):
        """Create a trading input widget."""
        return SpyderWidgetFactory.create_trading_input(input_type, label)
    
    def create_searchable_combo(items=None):
        """Create a searchable combo box widget."""
        return SpyderWidgetFactory.create_searchable_combo(items)
    
    def create_collapsible_group(title="", expanded=True):
        """Create a collapsible group widget."""
        return SpyderWidgetFactory.create_collapsible_group(title, expanded)
    
    # Add convenience functions to exports
    __all__.extend([
        "create_strike_range_slider",
        "create_trading_input", 
        "create_searchable_combo",
        "create_collapsible_group"
    ])
    
    print("✅ SpyderG_GUI: Enhanced widget convenience functions available")
    
except ImportError:
    print("⚠️  SpyderG_GUI: Enhanced widgets not available (missing dependencies)")

# Quick availability check for enhanced features
def check_enhanced_features():
    """Check availability of enhanced GUI features."""
    features = {
        "finplot_charts": False,
        "memory_monitoring": False,
        "professional_styling": False,
        "enhanced_widgets": False
    }
    
    try:
        import finplot
        features["finplot_charts"] = True
    except ImportError:
        pass
    
    try:
        import psutil
        features["memory_monitoring"] = True
    except ImportError:
        pass
    
    try:
        import qdarkstyle
        features["professional_styling"] = True
    except ImportError:
        pass
    
    try:
        import superqt
        features["enhanced_widgets"] = True
    except ImportError:
        pass
    
    return features

# Add feature check to exports
__all__.append("check_enhanced_features")