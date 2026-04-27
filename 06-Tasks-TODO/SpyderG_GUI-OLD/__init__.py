#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderG_GUI
Purpose: Graphical user interface components and dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-02

Package Description:
    The SpyderG_GUI package provides comprehensive graphical user interface
    components for the Spyder trading system including the main dashboard,
    trading widgets, chart displays, option chain visualization, and
    real-time monitoring interfaces. Built with PySide6 for modern UI.

Modules Overview:
    • SpyderG00_ApplicationManager: Qt application lifecycle management
    • SpyderG01_MainWindow: Main application window and layout
    • SpyderG02_GUIEntry: GUI entry point and initialization
    • SpyderG03_OptionChainWidget: Options chain display widget
    • SpyderG04_ChartWidget: Trading chart visualization
    • SpyderG05_TradingDashboard: Main trading dashboard
    • SpyderG06_DashboardData: Shared data models and dark-theme constants
    • SpyderG09_RiskParametersDialog: Interactive risk parameter configuration
    • SpyderG13_EnhancedWidgets: Custom enhanced UI widgets
    • SpyderG15_ConnectAPIStatus: Real-time broker/data feed connection status
    • SpyderG16_CircuitBreakerMonitor: Circuit breaker state monitoring
    • SpyderG29_ChartWidgetPlotly: Plotly-based chart widget
    • SpyderG30_PlotlyDataBridge: Data bridge for Plotly charts
    • SpyderG31_PlotlyTemplates: Templates for Plotly charts
    • SpyderG32_AgentHealthDashboard: Real-time X/Y-series agent health panel

Key Features:
    • Modern PySide6-based interface
    • Real-time data visualization
    • Interactive trading controls
    • Options chain analysis
    • System monitoring dashboard
"""

import logging

__version__ = "3.0.1"
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
        AppConfig,
    )

    __all__.extend(
        [
            "get_application_manager",
            "ensure_qt_application",
            "create_safe_widget",
            "init_gui_application",
            "init_headless_application",
            "is_qt_available",
            "get_app_info",
            "DisplayMode",
            "AppConfig",
        ]
    )
    logging.info("✅ SpyderG_GUI: Application Manager loaded successfully")
except Exception as e:
    logging.info("⚠️ SpyderG_GUI: Application Manager not available: %s", e)

# Import GUI modules with error handling and proper initialization
modules_to_import = [
    ("SpyderG01_MainWindow", "SpyderMainWindow"),
    ("SpyderG02_GUIEntry", "gui_main"),
    ("SpyderG03_OptionChainWidget", "OptionChainWidget"),
    ("SpyderG04_ChartWidget", "ChartWidget"),
    # G05_TradingDashboard imported lazily to avoid circular imports
    # Use create_trading_dashboard() or import directly when needed
    (
        "SpyderG09_RiskParametersDialog",
        ["RiskParametersDialog", "show_risk_parameters_dialog"],
    ),
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
            module = __import__(
                f".{module_name}", globals(), locals(), items_to_import, 1
            )
            for item in items_to_import:
                globals()[item] = getattr(module, item)
                __all__.append(item)
        else:
            # Import single class normally
            module = __import__(
                f".{module_name}", globals(), locals(), [items_to_import], 1
            )
            globals()[items_to_import] = getattr(module, items_to_import)
            __all__.append(items_to_import)

        logging.info("✅ SpyderG_GUI: %s loaded successfully", module_name)
        successful_imports += 1
    except Exception as e:
        logging.info("⚠️ SpyderG_GUI: %s not available: %s", module_name, e)

logging.info("✅ SpyderG_GUI: %s components loaded successfully", successful_imports)

# Import broker status widget (Tradier + Massive)
try:
    from .SpyderG15_ConnectAPIStatus import (
        BrokerStatusWidget,
        StatusConfig,
        StatusLevel,
        create_status_widget,
    )
    __all__.extend([
        "BrokerStatusWidget",
        "StatusConfig", "StatusLevel", "create_status_widget",
    ])
    logging.info("✅ SpyderG_GUI: BrokerStatusWidget loaded successfully")
except Exception as e:
    logging.info("⚠️ SpyderG_GUI: BrokerStatusWidget not available: %s", e)

# Import circuit breaker monitor
try:
    from .SpyderG16_CircuitBreakerMonitor import (
        CircuitBreakerMonitor,
        create_circuit_breaker_monitor,
    )
    __all__.extend(["CircuitBreakerMonitor", "create_circuit_breaker_monitor"])
    logging.info("✅ SpyderG_GUI: CircuitBreakerMonitor loaded successfully")
except Exception as e:
    logging.info("⚠️ SpyderG_GUI: CircuitBreakerMonitor not available: %s", e)


# Import agent health dashboard (v2 addition)
try:
    from .SpyderG32_AgentHealthDashboard import AgentHealthDashboard
    __all__.extend(["AgentHealthDashboard"])
    logging.info("✅ SpyderG_GUI: AgentHealthDashboard loaded successfully")
except Exception as e:
    logging.info("⚠️ SpyderG_GUI: AgentHealthDashboard not available: %s", e)


# Add convenience functions for safe widget creation
def create_trading_dashboard(*args, **kwargs):
    """Create trading dashboard with proper Qt initialization."""
    try:
        # Ensure Qt application is initialized
        if not ensure_qt_application():
            logging.info("Failed to initialize Qt application")
            return None

        # Import and create dashboard
        from .SpyderG05_TradingDashboard import SpyderTradingDashboard

        return create_safe_widget(SpyderTradingDashboard, *args, **kwargs)
    except Exception as e:
        logging.info("Failed to create trading dashboard: %s", e)
        return None


def create_chart_widget(*args, **kwargs):
    """Create chart widget with proper Qt initialization."""
    try:
        # Ensure Qt application is initialized
        if not ensure_qt_application():
            logging.info("Failed to initialize Qt application")
            return None

        # Import and create chart widget
        from .SpyderG04_ChartWidget import ChartWidget

        return create_safe_widget(ChartWidget, *args, **kwargs)
    except Exception as e:
        logging.info("Failed to create chart widget: %s", e)
        return None


def create_main_window(*args, **kwargs):
    """Create main window with proper Qt initialization."""
    try:
        # Ensure Qt application is initialized
        if not ensure_qt_application():
            logging.info("Failed to initialize Qt application")
            return None

        # Import and create main window
        from .SpyderG01_MainWindow import SpyderMainWindow

        return create_safe_widget(SpyderMainWindow, *args, **kwargs)
    except Exception as e:
        logging.info("Failed to create main window: %s", e)
        return None


# Add convenience functions to exports
__all__.extend(
    ["create_trading_dashboard", "create_chart_widget", "create_main_window"]
)


# Check for optional dependencies and provide warnings
def check_optional_dependencies():
    """Check for optional GUI dependencies."""
    dependencies = {
        "superqt": "Advanced Qt widgets",
        "matplotlib": "Chart plotting",
        "plotly": "Interactive charts",
        "finplot": "Financial plotting",
    }

    missing = []
    for dep, description in dependencies.items():
        try:
            __import__(dep)
        except ImportError:
            missing.append(f"{dep} ({description})")

    if missing:
        logging.info("Warning: Optional dependencies not available:")
        for dep in missing:
            logging.info("  - %s", dep)
        logging.info("Install with: pip install [package_name]")


# Run dependency check
try:
    check_optional_dependencies()
except Exception as e:
    logging.debug("Optional dependency check failed: %s", e)

# Initialize application manager for headless testing by default
try:
    # Auto-detect display mode
    import os

    if "DISPLAY" not in os.environ or os.environ.get("QT_QPA_PLATFORM") in [
        "minimal",
        "offscreen",
    ]:
        # Headless mode
        init_headless_application()
    else:
        # GUI mode available
        pass  # Don't auto-initialize GUI mode, let user choose
except Exception as e:
    logging.debug("Optional GUI init failed: %s", e)

# G11, G12, G99 — additional GUI modules
try:
    from .SpyderG11_SkewMonitorDialog import SkewMonitorDialog
    __all__.extend(["SkewMonitorDialog"])
except ImportError as e:
    logging.info("Warning: SpyderG11_SkewMonitorDialog not available: %s", e)

try:
    from .SpyderG12_SignalInfoDialog import SignalInfoDialog
    __all__.extend(["SignalInfoDialog"])
except ImportError as e:
    logging.info("Warning: SpyderG12_SignalInfoDialog not available: %s", e)

try:
    from .SpyderG99_GUILogHandler import GUILogHandler, FilteredGUILogHandler
    __all__.extend(["GUILogHandler", "FilteredGUILogHandler"])
except ImportError as e:
    logging.info("Warning: SpyderG99_GUILogHandler not available: %s", e)

try:
    from .SpyderG06_DashboardData import MarketData, SignalData
    __all__.extend(["MarketData", "SignalData"])
except ImportError as e:
    logging.info("Warning: SpyderG06_DashboardData not available: %s", e)

try:
    from .SpyderG13_EnhancedWidgets import (
        SpyderStrikeRangeSlider, SpyderTradingInput,
        SpyderSearchableCombo, SpyderCollapsibleGroup,
    )
    __all__.extend(["SpyderStrikeRangeSlider", "SpyderTradingInput",
                    "SpyderSearchableCombo", "SpyderCollapsibleGroup"])
except ImportError as e:
    logging.info("Warning: SpyderG13_EnhancedWidgets not available: %s", e)

try:
    from .SpyderG29_ChartWidgetPlotly import PlotlyChartWidget
    __all__.extend(["PlotlyChartWidget"])
except ImportError as e:
    logging.info("Warning: SpyderG29_ChartWidgetPlotly not available: %s", e)

try:
    from .SpyderG30_PlotlyDataBridge import PlotlyDataBridge, SpyderToPlotlyConverter
    __all__.extend(["PlotlyDataBridge", "SpyderToPlotlyConverter"])
except ImportError as e:
    logging.info("Warning: SpyderG30_PlotlyDataBridge not available: %s", e)

try:
    from .SpyderG31_PlotlyTemplates import (
        CandlestickChartTemplate, OptionsChartTemplate, VolatilityChartTemplate,
    )
    __all__.extend(["CandlestickChartTemplate", "OptionsChartTemplate",
                    "VolatilityChartTemplate"])
except ImportError as e:
    logging.info("Warning: SpyderG31_PlotlyTemplates not available: %s", e)

logging.info("✅ SpyderG_GUI package initialized (v%s)", __version__)

# Export version
__all__.append("__version__")
