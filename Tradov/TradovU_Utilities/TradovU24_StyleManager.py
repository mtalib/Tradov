#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: Tradov.TradovU_Utilities
Module: TradovU24_StyleManager.py
Purpose: Professional theme and styling management with QDarkStyleSheet integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-13 Time: 16:15:00

Module Description:
    This module provides comprehensive styling and theme management for the Tradov
    trading system. It integrates QDarkStyleSheet for professional appearance while
    maintaining the exact visual identity of the existing dashboard. Includes support
    for qtawesome icons and custom color overrides for trading-specific elements.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import sys
from typing import Any
from pathlib import Path

# ==============================================================================
# PYTHON PATH SETUP
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

# QDarkStyleSheet integration
try:
    import qdarkstyle
    from qdarkstyle import DarkPalette, LightPalette  # noqa: F401
    QDARKSTYLE_AVAILABLE = True
except ImportError:
    QDARKSTYLE_AVAILABLE = False
    logging.debug("Optional dependency qdarkstyle not available. Install with: pip install qdarkstyle")

# QtAwesome icons integration
try:
    import qtawesome as qta
    QTAWESOME_AVAILABLE = True
except ImportError:
    QTAWESOME_AVAILABLE = False
    logging.debug("Optional dependency qtawesome not available. Install with: pip install qtawesome")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger  # noqa: E402
import logging  # noqa: E402

# ==============================================================================
# TRADOV COLOR SCHEME - Exact match to existing dashboard
# ==============================================================================
class TradovColors:
    """Tradov trading system color constants."""

    # Base colors - matching existing dashboard exactly
    BACKGROUND = "#0a0a0a"
    PANEL = "#1a1a1a"
    BORDER = "#333333"
    TEXT = "#ffffff"

    # Trading colors
    POSITIVE = "#00ff41"      # Green for profits/buy
    NEGATIVE = "#FF073A"      # Electric Crimson — losses/sell
    NEUTRAL = "#ffd700"       # Gold for neutral/warning
    WARNING = "#ff9800"       # Orange for caution
    INFO = "#00ffff"          # Cyan for information

    # Status colors
    SUCCESS = "#4caf50"
    ERROR = "#FF073A"
    DISABLED = "#666666"

    # Chart colors
    VOLUME_COLOR = "#4d4d4d"
    GRID_COLOR = "#2a2a2a"

    # Special trading colors
    BID_COLOR = "#00ff41"
    ASK_COLOR = "#FF073A"
    SPREAD_COLOR = "#ffd700"

    # Option chain colors
    ITM_COLOR = "#ffe0b3"     # In-the-money options
    OTM_COLOR = "#e0e0e0"     # Out-of-the-money options
    ATM_COLOR = "#fff3cd"     # At-the-money options

# ==============================================================================
# ICON MAPPINGS
# ==============================================================================
class TradovIcons:
    """Professional icon mappings using QtAwesome."""

    # Trading icons
    BUY = "fa5s.arrow-up"
    SELL = "fa5s.arrow-down"
    PROFIT = "fa5s.chart-line"
    LOSS = "fa5s.chart-line-down"

    # Dashboard icons
    SETTINGS = "fa5s.cog"
    REFRESH = "fa5s.sync-alt"
    PLAY = "fa5s.play"
    PAUSE = "fa5s.pause"
    STOP = "fa5s.stop"

    # Chart icons
    ZOOM_IN = "fa5s.search-plus"
    ZOOM_OUT = "fa5s.search-minus"
    ZOOM_RESET = "fa5s.expand-arrows-alt"

    # Navigation icons
    HOME = "fa5s.home"
    CHART = "fa5s.chart-area"
    TABLE = "fa5s.table"
    ORDERS = "fa5s.list-ul"

    # Status icons
    CONNECTED = "fa5s.wifi"
    DISCONNECTED = "fa5s.exclamation-triangle"
    WARNING = "fa5s.exclamation-circle"
    ERROR = "fa5s.times-circle"
    SUCCESS = "fa5s.check-circle"

    # Memory/Performance
    MEMORY = "fa5s.memory"
    CPU = "fa5s.microchip"
    PERFORMANCE = "fa5s.tachometer-alt"

# ==============================================================================
# STYLE MANAGER CLASS
# ==============================================================================
class TradovStyleManager:
    """
    Professional style and theme manager for Tradov trading system.

    Features:
    - QDarkStyleSheet integration with custom overrides
    - QtAwesome icon management
    - Consistent color scheme enforcement
    - Theme switching capabilities
    - Custom trading-specific styling
    """

    def __init__(self):
        """Initialize the style manager."""
        self.logger = TradovLogger.get_logger(self.__class__.__name__)

        # Current theme state
        self.current_theme = "dark"
        self.qdarkstyle_enabled = QDARKSTYLE_AVAILABLE
        self.qtawesome_enabled = QTAWESOME_AVAILABLE

        # Style caches
        self._base_stylesheet = ""
        self._custom_overrides = ""
        self._final_stylesheet = ""

        # Initialize
        self._initialize_style_system()

        self.logger.info("Style manager initialized - QDarkStyle: %s, QtAwesome: %s", self.qdarkstyle_enabled, self.qtawesome_enabled)  # noqa: E501

    def _initialize_style_system(self):
        """Initialize the styling system."""
        # Generate base stylesheet
        if self.qdarkstyle_enabled:
            self._base_stylesheet = qdarkstyle.load_stylesheet(qt_api='pyside6')
        else:
            self._base_stylesheet = self._generate_fallback_stylesheet()

        # Generate custom overrides
        self._custom_overrides = self._generate_tradov_overrides()

        # Combine styles
        self._final_stylesheet = self._base_stylesheet + "\n" + self._custom_overrides

    def _generate_fallback_stylesheet(self) -> str:
        """Generate fallback stylesheet when QDarkStyleSheet unavailable."""
        return f"""
        /* Fallback Dark Theme */
        QWidget {{
            background-color: {TradovColors.PANEL};
            color: {TradovColors.TEXT};
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
        }}

        QMainWindow {{
            background-color: {TradovColors.BACKGROUND};
        }}

        QPushButton {{
            background-color: #2a2a2a;
            border: 1px solid {TradovColors.BORDER};
            color: {TradovColors.TEXT};
            padding: 5px 10px;
            border-radius: 3px;
        }}

        QPushButton:hover {{
            background-color: #3a3a3a;
        }}

        QPushButton:pressed {{
            background-color: #1a1a1a;
        }}

        QLineEdit, QComboBox {{
            background-color: {TradovColors.BACKGROUND};
            border: 1px solid {TradovColors.BORDER};
            color: {TradovColors.TEXT};
            padding: 3px;
            border-radius: 2px;
        }}

        QTableWidget {{
            background-color: {TradovColors.PANEL};
            alternate-background-color: #252525;
            gridline-color: {TradovColors.BORDER};
        }}

        QHeaderView::section {{
            background-color: #2a2a2a;
            color: {TradovColors.TEXT};
            border: 1px solid {TradovColors.BORDER};
            padding: 3px;
        }}
        """

    def _generate_tradov_overrides(self) -> str:
        """Generate Tradov-specific style overrides."""
        return f"""

        /* ===================================================================== */
        /* TRADOV TRADING SYSTEM CUSTOM OVERRIDES */
        /* ===================================================================== */

        /* Trading Dashboard Specific Styles */
        QWidget#TradingDashboard {{
            background-color: {TradovColors.BACKGROUND};
        }}

        /* Chart Widget Styling */
        QWidget#ChartWidget {{
            background-color: {TradovColors.PANEL};
            border: 1px solid {TradovColors.BORDER};
        }}

        /* Control Panel Buttons */
        QPushButton#TradingButton {{
            background-color: #2a2a2a;
            color: {TradovColors.TEXT};
            border: 1px solid {TradovColors.BORDER};
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: normal;
        }}

        QPushButton#TradingButton:hover {{
            background-color: #3a3a3a;
            border-color: {TradovColors.INFO};
        }}

        QPushButton#TradingButton:checked {{
            background-color: {TradovColors.POSITIVE};
            color: #000000;
            border-color: {TradovColors.POSITIVE};
        }}

        /* Buy/Sell Buttons */
        QPushButton#BuyButton {{
            background-color: {TradovColors.POSITIVE};
            color: #000000;
            border: 2px solid {TradovColors.POSITIVE};
            font-weight: normal;
            padding: 8px 15px;
        }}

        QPushButton#BuyButton:hover {{
            background-color: #00e03a;
        }}

        QPushButton#SellButton {{
            background-color: {TradovColors.NEGATIVE};
            color: #ffffff;
            border: 2px solid {TradovColors.NEGATIVE};
            font-weight: normal;
            padding: 8px 15px;
        }}

        QPushButton#SellButton:hover {{
            background-color: #CC062E;
        }}

        /* Status Indicators */
        QLabel#StatusConnected {{
            color: {TradovColors.POSITIVE};
            font-weight: normal;
        }}

        QLabel#StatusDisconnected {{
            color: {TradovColors.NEGATIVE};
            font-weight: normal;
        }}

        QLabel#StatusWarning {{
            color: {TradovColors.WARNING};
            font-weight: normal;
        }}

        /* Price Display Labels */
        QLabel#PricePositive {{
            color: {TradovColors.POSITIVE};
            font-weight: normal;
            font-size: 12pt;
        }}

        QLabel#PriceNegative {{
            color: {TradovColors.NEGATIVE};
            font-weight: normal;
            font-size: 12pt;
        }}

        QLabel#PriceNeutral {{
            color: {TradovColors.NEUTRAL};
            font-weight: normal;
            font-size: 12pt;
        }}

        /* Option Chain Table */
        QTableWidget#OptionChain {{
            background-color: {TradovColors.PANEL};
            alternate-background-color: #252525;
            gridline-color: {TradovColors.BORDER};
            selection-background-color: {TradovColors.INFO};
        }}

        QTableWidget#OptionChain::item:selected {{
            background-color: {TradovColors.INFO};
            color: #000000;
        }}

        /* Call Options */
        QTableWidget#OptionChain QTableWidgetItem[data-option-type="call"] {{
            background-color: rgba(0, 255, 65, 0.1);
        }}

        /* Put Options */
        QTableWidget#OptionChain QTableWidgetItem[data-option-type="put"] {{
            background-color: rgba(255, 23, 68, 0.1);
        }}

        /* Memory Monitor */
        QLabel#MemoryLow {{
            color: {TradovColors.SUCCESS};
            font-size: 8pt;
        }}

        QLabel#MemoryMedium {{
            color: {TradovColors.WARNING};
            font-size: 8pt;
        }}

        QLabel#MemoryHigh {{
            color: {TradovColors.NEGATIVE};
            font-size: 8pt;
        }}

        /* Progress Bars */
        QProgressBar {{
            border: 1px solid {TradovColors.BORDER};
            border-radius: 3px;
            text-align: center;
            background-color: {TradovColors.BACKGROUND};
        }}

        QProgressBar::chunk {{
            background-color: {TradovColors.POSITIVE};
            border-radius: 2px;
        }}

        /* Group Boxes */
        QGroupBox {{
            font-weight: normal;
            border: 2px solid {TradovColors.BORDER};
            border-radius: 5px;
            margin-top: 1ex;
            color: {TradovColors.TEXT};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: {TradovColors.INFO};
        }}

        /* Splitters */
        QSplitter::handle {{
            background-color: {TradovColors.BORDER};
        }}

        QSplitter::handle:horizontal {{
            width: 3px;
        }}

        QSplitter::handle:vertical {{
            height: 3px;
        }}

        /* Scroll Bars */
        QScrollBar:vertical {{
            background-color: {TradovColors.PANEL};
            width: 12px;
            border: none;
        }}

        QScrollBar::handle:vertical {{
            background-color: {TradovColors.BORDER};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {TradovColors.INFO};
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {TradovColors.BACKGROUND};
            color: {TradovColors.TEXT};
            border: 1px solid {TradovColors.BORDER};
            padding: 5px;
            border-radius: 3px;
        }}

        /* Menu Bars */
        QMenuBar {{
            background-color: {TradovColors.PANEL};
            color: {TradovColors.TEXT};
        }}

        QMenuBar::item {{
            background-color: transparent;
            padding: 4px 8px;
        }}

        QMenuBar::item:selected {{
            background-color: {TradovColors.INFO};
            color: #000000;
        }}

        QMenu {{
            background-color: {TradovColors.PANEL};
            color: {TradovColors.TEXT};
            border: 1px solid {TradovColors.BORDER};
        }}

        QMenu::item:selected {{
            background-color: {TradovColors.INFO};
            color: #000000;
        }}

        /* Tab Widgets */
        QTabWidget::pane {{
            border: 1px solid {TradovColors.BORDER};
            background-color: {TradovColors.PANEL};
        }}

        QTabBar::tab {{
            background-color: #2a2a2a;
            color: {TradovColors.TEXT};
            padding: 5px 10px;
            border: 1px solid {TradovColors.BORDER};
            border-bottom: none;
        }}

        QTabBar::tab:selected {{
            background-color: {TradovColors.INFO};
            color: #000000;
        }}

        /* Custom Animation Classes */
        .profit-flash {{
            background-color: {TradovColors.POSITIVE};
            animation: flash 0.5s;
        }}

        .loss-flash {{
            background-color: {TradovColors.NEGATIVE};
            animation: flash 0.5s;
        }}

        @keyframes flash {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        """

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def apply_style(self, app: QApplication = None, widget: QWidget = None):
        """Apply the Tradov style to application or widget."""
        if app:
            app.setStyleSheet(self._final_stylesheet)
            self.logger.info("Applied Tradov style to application")
        elif widget:
            widget.setStyleSheet(self._final_stylesheet)
            self.logger.info("Applied Tradov style to %s", widget.__class__.__name__)

    def get_stylesheet(self) -> str:
        """Get the complete stylesheet."""
        return self._final_stylesheet

    def get_icon(self, icon_name: str, color: str = None, size: int = 16) -> Any:
        """Get a professional icon using QtAwesome."""
        if not self.qtawesome_enabled:
            return None

        try:
            # Get icon from TradovIcons mapping
            icon_code = getattr(TradovIcons, icon_name.upper(), icon_name)

            # Create icon with specified color and size
            options = {'scale_factor': size / 16}
            if color:
                options['color'] = color
            else:
                options['color'] = TradovColors.TEXT

            return qta.icon(icon_code, **options)

        except Exception as e:
            self.logger.error("Failed to create icon %s: %s", icon_name, e)
            return None

    def get_color(self, color_name: str) -> str:
        """Get a color from the Tradov color scheme."""
        return getattr(TradovColors, color_name.upper(), TradovColors.TEXT)

    def apply_trading_button_style(self, button, button_type: str = "normal"):
        """Apply specific styling to trading buttons."""
        if button_type == "buy":
            button.setObjectName("BuyButton")
            button.setStyleSheet(f"""
                QPushButton#BuyButton {{
                    background-color: {TradovColors.POSITIVE};
                    color: #000000;
                    border: 2px solid {TradovColors.POSITIVE};
                    font-weight: normal;
                    padding: 8px 15px;
                    border-radius: 5px;
                }}
                QPushButton#BuyButton:hover {{
                    background-color: #00e03a;
                }}
            """)
        elif button_type == "sell":
            button.setObjectName("SellButton")
            button.setStyleSheet(f"""
                QPushButton#SellButton {{
                    background-color: {TradovColors.NEGATIVE};
                    color: #ffffff;
                    border: 2px solid {TradovColors.NEGATIVE};
                    font-weight: normal;
                    padding: 8px 15px;
                    border-radius: 5px;
                }}
                QPushButton#SellButton:hover {{
                    background-color: #CC062E;
                }}
            """)
        else:
            button.setObjectName("TradingButton")

    def apply_status_style(self, label, status: str):
        """Apply status-specific styling to labels."""
        if status == "connected":
            label.setObjectName("StatusConnected")
        elif status == "disconnected":
            label.setObjectName("StatusDisconnected")
        elif status == "warning":
            label.setObjectName("StatusWarning")

    def apply_price_style(self, label, price_change: float):
        """Apply price-specific styling based on price change."""
        if price_change > 0:
            label.setObjectName("PricePositive")
        elif price_change < 0:
            label.setObjectName("PriceNegative")
        else:
            label.setObjectName("PriceNeutral")

    def apply_memory_style(self, label, memory_percent: float):
        """Apply memory usage styling."""
        if memory_percent < 50:
            label.setObjectName("MemoryLow")
        elif memory_percent < 80:
            label.setObjectName("MemoryMedium")
        else:
            label.setObjectName("MemoryHigh")

    # ==========================================================================
    # THEME MANAGEMENT
    # ==========================================================================
    def switch_theme(self, theme: str = "dark"):
        """Switch between themes (future expansion)."""
        if theme == "dark":
            self.current_theme = "dark"
            self._initialize_style_system()
        # Future: implement light theme
        self.logger.info("Switched to %s theme", theme)

    def refresh_styles(self):
        """Refresh and regenerate all styles."""
        self._initialize_style_system()
        self.logger.info("Styles refreshed")

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def is_qdarkstyle_available(self) -> bool:
        """Check if QDarkStyleSheet is available."""
        return self.qdarkstyle_enabled

    def is_qtawesome_available(self) -> bool:
        """Check if QtAwesome is available."""
        return self.qtawesome_enabled

    def get_theme_info(self) -> dict[str, Any]:
        """Get current theme information."""
        return {
            'current_theme': self.current_theme,
            'qdarkstyle_enabled': self.qdarkstyle_enabled,
            'qtawesome_enabled': self.qtawesome_enabled,
            'colors_available': len([attr for attr in dir(TradovColors) if not attr.startswith('_')]),  # noqa: E501
            'icons_available': len([attr for attr in dir(TradovIcons) if not attr.startswith('_')])
        }

# ==============================================================================
# GLOBAL STYLE MANAGER
# ==============================================================================
_global_style_manager = None

def get_style_manager() -> TradovStyleManager:
    """Get the global style manager instance."""
    global _global_style_manager
    if _global_style_manager is None:
        _global_style_manager = TradovStyleManager()
    return _global_style_manager

def apply_tradov_style(app: QApplication = None, widget: QWidget = None):
    """Apply Tradov styling to application or widget."""
    manager = get_style_manager()
    manager.apply_style(app, widget)

def get_tradov_icon(icon_name: str, color: str = None, size: int = 16):
    """Get a Tradov icon."""
    manager = get_style_manager()
    return manager.get_icon(icon_name, color, size)

def get_tradov_color(color_name: str) -> str:
    """Get a Tradov color."""
    manager = get_style_manager()
    return manager.get_color(color_name)

# ==============================================================================
# TESTING AND DEMONSTRATION
# ==============================================================================
def main():
    """Demonstrate style manager capabilities."""
    logging.info("Tradov Style Manager Demo")
    logging.info("=" * 50)

    # Create style manager
    manager = TradovStyleManager()

    # Show theme info
    info = manager.get_theme_info()
    logging.info("Theme Information:")
    for key, value in info.items():
        logging.info("  %s: %s", key, value)

    # Test color access
    logging.info("\nColor Examples:")
    logging.info("  Positive: %s", manager.get_color('positive'))
    logging.info("  Negative: %s", manager.get_color('negative'))
    logging.info("  Neutral: %s", manager.get_color('neutral'))

    # Test icon availability
    if manager.is_qtawesome_available():
        logging.info("\nIcon system available")
    else:
        logging.info("\nIcon system not available (install qtawesome)")

    # Show stylesheet length
    stylesheet = manager.get_stylesheet()
    logging.info("\nStylesheet generated: %s characters", len(stylesheet))

if __name__ == "__main__":
    main()
