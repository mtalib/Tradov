#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - GUI Package (Updated with Application Manager)
Graphical User Interface components for the Spyder trading system
"""

__version__ = '2.1.0'
__all__ = []

# Import application manager first
try:
    from .SpyderG00_ApplicationManager import (
        get_application_manager, 
        ensure_qt_application,
        create_safe_widget,
        init_gui_application,
        init_headless_application,
        is_qt_available,
        get_app_info,
        DisplayMode,
        AppConfig
    )
    __all__.extend([
        'get_application_manager', 
        'ensure_qt_application',
        'create_safe_widget', 
        'init_gui_application',
        'init_headless_application',
        'is_qt_available',
        'get_app_info',
        'DisplayMode',
        'AppConfig'
    ])
    print("✅ SpyderG_GUI: Application Manager loaded successfully")
except Exception as e:
    print(f"⚠️ SpyderG_GUI: Application Manager not available: {e}")

# Import GUI modules with error handling and proper initialization
modules_to_import = [
    ("SpyderG01_MainWindow", "SpyderMainWindow"),
    ("SpyderG02_GUIEntry", "gui_main"),
    ("SpyderG03_OptionChainWidget", "OptionChainWidget"),
    ("SpyderG04_ChartWidget", "ChartWidget"),
    ("SpyderG05_TradingDashboard", "SpyderTradingDashboard"),
    ("SpyderG06_RiskParametersDialog", ["RiskParametersDialog", "show_risk_parameters_dialog"]),
]

successful_imports = 0

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
        successful_imports += 1
    except Exception as e:
        print(f"⚠️ SpyderG_GUI: {module_name} not available: {e}")

print(f"✅ SpyderG_GUI: {successful_imports} components loaded successfully")

# Add convenience functions for safe widget creation
def create_trading_dashboard(*args, **kwargs):
    """Create trading dashboard with proper Qt initialization."""
    try:
        # Ensure Qt application is initialized
        if not ensure_qt_application():
            print("Failed to initialize Qt application")
            return None
        
        # Import and create dashboard
        from .SpyderG05_TradingDashboard import SpyderTradingDashboard
        return create_safe_widget(SpyderTradingDashboard, *args, **kwargs)
    except Exception as e:
        print(f"Failed to create trading dashboard: {e}")
        return None

def create_chart_widget(*args, **kwargs):
    """Create chart widget with proper Qt initialization."""
    try:
        # Ensure Qt application is initialized
        if not ensure_qt_application():
            print("Failed to initialize Qt application")
            return None
        
        # Import and create chart widget
        from .SpyderG04_ChartWidget import ChartWidget
        return create_safe_widget(ChartWidget, *args, **kwargs)
    except Exception as e:
        print(f"Failed to create chart widget: {e}")
        return None

def create_main_window(*args, **kwargs):
    """Create main window with proper Qt initialization."""
    try:
        # Ensure Qt application is initialized
        if not ensure_qt_application():
            print("Failed to initialize Qt application")
            return None
        
        # Import and create main window
        from .SpyderG01_MainWindow import SpyderMainWindow
        return create_safe_widget(SpyderMainWindow, *args, **kwargs)
    except Exception as e:
        print(f"Failed to create main window: {e}")
        return None

# Add convenience functions to exports
__all__.extend([
    'create_trading_dashboard',
    'create_chart_widget', 
    'create_main_window'
])

# Check for optional dependencies and provide warnings
def check_optional_dependencies():
    """Check for optional GUI dependencies."""
    dependencies = {
        'superqt': 'Advanced Qt widgets',
        'matplotlib': 'Chart plotting',
        'plotly': 'Interactive charts',
        'finplot': 'Financial plotting'
    }
    
    missing = []
    for dep, description in dependencies.items():
        try:
            __import__(dep)
        except ImportError:
            missing.append(f"{dep} ({description})")
    
    if missing:
        print("Warning: Optional dependencies not available:")
        for dep in missing:
            print(f"  - {dep}")
        print("Install with: pip install [package_name]")

# Run dependency check
try:
    check_optional_dependencies()
except Exception:
    pass

# Initialize application manager for headless testing by default
try:
    # Auto-detect display mode
    import os
    if 'DISPLAY' not in os.environ or os.environ.get('QT_QPA_PLATFORM') in ['minimal', 'offscreen']:
        # Headless mode
        init_headless_application()
    else:
        # GUI mode available
        pass  # Don't auto-initialize GUI mode, let user choose
except Exception:
    pass

print(f"✅ SpyderG_GUI package initialized (v{__version__})")

# Export version
__all__.append("__version__")