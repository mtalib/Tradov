#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG13_EnhancedWidgets.py
Purpose: Enhanced UI widgets with superqt integration for superior user experience
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-13 Time: 17:00:00

Module Description:
    This module provides enhanced UI widgets using superqt for the Spyder trading
    system. It includes multi-handle sliders for option strike selection, enhanced
    tooltips with trading data, improved combo boxes with search functionality,
    and specialized trading input widgets with validation. All widgets maintain
    the Spyder visual theme and provide superior user experience.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
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
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen

# Enhanced widgets from superqt
try:
    from superqt import QRangeSlider, QSearchableComboBox, QCollapsibleGroupBox
    from superqt.utils import signals_blocked  # noqa: F401
    SUPERQT_AVAILABLE = True
except ImportError:
    SUPERQT_AVAILABLE = False
    logging.info("Warning: superqt not available. Install with: pip install superqt")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU24_StyleManager import SpyderColors, get_style_manager

logger = logging.getLogger(__name__)

try:
    from Spyder.SpyderG_GUI.SpyderG12_SignalInfoDialog import SignalInfoDialog

    signal_dialog_available = True
    logger.info("✅ Signal Info Dialog module available")
except ImportError:
    SignalInfoDialog = None  # type: ignore
    signal_dialog_available = False
    logger.info("⚠️ Signal Info Dialog not available - using fallback QMessageBox")

SkewMonitorDialog = None  # type: ignore
skew_dialog_available = None

MarketInternalsDialog = None  # type: ignore
internals_dialog_available = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Widget animation durations
ANIMATION_DURATION = 200  # milliseconds
TOOLTIP_DELAY = 500       # milliseconds

# Validation constants
MIN_STRIKE_PRICE = 1.0
MAX_STRIKE_PRICE = 10000.0
MIN_QUANTITY = 1
MAX_QUANTITY = 10000
MIN_OPTION_PREMIUM = 0.01
MAX_OPTION_PREMIUM = 1000.0

SYMBOL_DESCRIPTIONS = {
    "SPY": "SPDR S&P 500 ETF - Most liquid S&P 500 ETF",
    "SPX": "S&P 500 Index - Cash index value",
    "VIX": "CBOE Volatility Index - 30-day implied volatility",
    "VIX9D": "CBOE 9-Day Volatility Index - Short-term volatility",
    "VXV": "CBOE 3-Month Volatility Index - 93-day implied volatility",
    "VVIX": "VIX of VIX - Volatility of volatility index",
    "$TICK": "NYSE Tick Index - Upticks minus downticks",
    "$TRIN": "Arms Index - Advance/Decline volume ratio",
    "$ADD": "Advance-Decline Line - Net advancing issues",
    "CPC": "Put/Call Ratio - Computed from SPY options chain volume (nearest expiry)",
    "SKEW": "CBOE Skew Index - Tail risk measure",
    "QQQ": "Invesco QQQ Trust - NASDAQ 100 ETF",
    "IWM": "iShares Russell 2000 ETF - Small caps",
    "10Y": "10-Year Treasury Yield (FRED DGS10 — risk-free rate)",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "LQD": "iShares Investment Grade Corporate Bond ETF",
    "DXY": "US Dollar Index (UUP ETF proxy — Tradier has no DXY index)",
    "GLD": "SPDR Gold Trust ETF - Gold proxy",
    "NAAIM": "NAAIM Exposure Index - Active manager equity allocation (0-200%)",
    "AABULL": "AAII Bull% (UMCSENT proxy) - Retail investor bullish sentiment",
    "GEX": "Gamma Exposure - Market maker hedging pressure",
    "DEX": "Delta Exposure - Directional hedging flow",
    "OGL": "Zero Gamma Level - Key support/resistance",
    "DIX": "Dark Index - Dark pool buying percentage",
    "SWAN": "Black Swan Risk Indicator - Tail risk monitor",
    "PMR": "Pivot Mean-Reversion Signal (S08) - DIS=disabled, ARMED=watching, fired shows direction/level/score",
}

COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#FF073A",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "automation_active": "#00b8d4",
    "connecting": "#00b8d4",
    "grid": "#2a2a2a",
    "orange": "#ff9800",
    "red": "#FF073A",
    "cyan": "#00ffff",
    "yellow": "#ffff00",
    "blue": "#4169E1",
    "purple": "#9370DB",
}

_TOOLTIP_APP_STYLE = """
QToolTip {
    color: #ffffff !important;
    background-color: #1a1a1a !important;
    border: 2px solid #555555 !important;
    padding: 8px !important;
    border-radius: 4px !important;
    font-size: 12px !important;
    font-weight: normal !important;
    opacity: 1.0 !important;
}
"""

_TOOLTIP_WIDGET_STYLE = """
QWidget {
    selection-background-color: #2a2a2a;
}
QWidget QToolTip {
    color: white !important;
    background-color: #1a1a1a !important;
    border: 2px solid #555555 !important;
    padding: 8px !important;
}
"""

_TOOLTIP_THEME_MARKER = "/* spyder-tooltip-theme */"


def apply_tooltip_theme(app, widget=None) -> None:
    """Install the dashboard's tooltip theme app-wide; idempotent across calls.

    Callable from the app bootstrap (preferred) or from a window constructor.
    Re-application is a no-op at the app level because the theme is tagged with
    a marker comment. The widget-level stylesheet is additive and harmless.
    """
    if app is not None:
        current = app.styleSheet() or ""
        if _TOOLTIP_THEME_MARKER not in current:
            app.setStyleSheet(current + _TOOLTIP_THEME_MARKER + _TOOLTIP_APP_STYLE)
    if widget is not None:
        widget.setStyleSheet((widget.styleSheet() or "") + _TOOLTIP_WIDGET_STYLE)

# ==============================================================================
# ENHANCED STRIKE RANGE SLIDER
# ==============================================================================
class SpyderStrikeRangeSlider(QWidget):
    """
    Enhanced range slider for selecting option strike price ranges.

    Features:
    - Dual-handle slider for range selection
    - Real-time value display
    - Trading-specific styling
    - Validation and constraints
    """

    # Signals
    range_changed = Signal(float, float)  # min_strike, max_strike

    def __init__(self, min_strike: float = 400.0, max_strike: float = 500.0, parent=None):
        """Initialize the strike range slider."""
        super().__init__(parent)

        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

        # Configuration
        self.min_value = min_strike
        self.max_value = max_strike
        self.current_min = min_strike
        self.current_max = max_strike

        # Setup UI
        self.setup_ui()

        # Apply styling
        self.apply_trading_style()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Title label
        title_label = QLabel("Strike Price Range")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"color: {SpyderColors.TEXT}; font-weight: normal;")
        layout.addWidget(title_label)

        # Value display
        value_layout = QHBoxLayout()

        self.min_label = QLabel(f"${self.current_min:.2f}")
        self.min_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.min_label.setStyleSheet(f"color: {SpyderColors.POSITIVE}; font-weight: normal;")

        self.max_label = QLabel(f"${self.current_max:.2f}")
        self.max_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.max_label.setStyleSheet(f"color: {SpyderColors.NEGATIVE}; font-weight: normal;")

        value_layout.addWidget(self.min_label)
        value_layout.addStretch()
        value_layout.addWidget(self.max_label)

        layout.addLayout(value_layout)

        # Range slider
        if SUPERQT_AVAILABLE:
            self.range_slider = QRangeSlider(Qt.Orientation.Horizontal)
            self.range_slider.setMinimum(int(self.min_value * 100))  # Convert to cents
            self.range_slider.setMaximum(int(self.max_value * 100))
            self.range_slider.setValue((int(self.current_min * 100), int(self.current_max * 100)))
            self.range_slider.valueChanged.connect(self._on_range_changed)
        else:
            # Fallback to single slider
            self.range_slider = QSlider(Qt.Orientation.Horizontal)
            self.range_slider.setMinimum(int(self.min_value * 100))
            self.range_slider.setMaximum(int(self.max_value * 100))
            self.range_slider.setValue(int(self.current_min * 100))
            self.range_slider.valueChanged.connect(self._on_single_slider_changed)

        layout.addWidget(self.range_slider)

        # Preset buttons
        preset_layout = QHBoxLayout()

        presets = [
            ("Tight", 0.95, 1.05),
            ("Normal", 0.90, 1.10),
            ("Wide", 0.85, 1.15)
        ]

        for name, min_factor, max_factor in presets:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, mf=min_factor, xf=max_factor: self._apply_preset(mf, xf))
            preset_layout.addWidget(btn)

        layout.addLayout(preset_layout)
        self.setLayout(layout)

    def _on_range_changed(self, values: tuple[int, int]):
        """Handle range slider value change."""
        min_val, max_val = values
        self.current_min = min_val / 100.0  # Convert back from cents
        self.current_max = max_val / 100.0

        self._update_labels()
        self.range_changed.emit(self.current_min, self.current_max)

    def _on_single_slider_changed(self, value: int):
        """Handle single slider change (fallback)."""
        self.current_min = value / 100.0
        self.current_max = self.current_min + 10.0  # Fixed range

        self._update_labels()
        self.range_changed.emit(self.current_min, self.current_max)

    def _update_labels(self):
        """Update the value display labels."""
        self.min_label.setText(f"${self.current_min:.2f}")
        self.max_label.setText(f"${self.current_max:.2f}")

    def _apply_preset(self, min_factor: float, max_factor: float):
        """Apply a preset range based on current center point."""
        center = (self.current_min + self.current_max) / 2
        new_min = center * min_factor
        new_max = center * max_factor

        self.set_range(new_min, new_max)

    def set_range(self, min_strike: float, max_strike: float):
        """Set the strike range programmatically."""
        self.current_min = max(min_strike, self.min_value)
        self.current_max = min(max_strike, self.max_value)

        if SUPERQT_AVAILABLE and hasattr(self.range_slider, 'setValue'):
            self.range_slider.setValue((int(self.current_min * 100), int(self.current_max * 100)))
        else:
            self.range_slider.setValue(int(self.current_min * 100))

        self._update_labels()

    def get_range(self) -> tuple[float, float]:
        """Get the current strike range."""
        return self.current_min, self.current_max

    def apply_trading_style(self):
        """Apply trading-specific styling."""
        style_manager = get_style_manager()
        style_manager.apply_style(widget=self)

# ==============================================================================
# ENHANCED TRADING INPUT WIDGET
# ==============================================================================
class SpyderTradingInput(QWidget):
    """
    Enhanced input widget for trading parameters with validation.

    Features:
    - Real-time validation
    - Visual feedback for errors
    - Trading-specific input types
    - Animated error states
    """

    # Signals
    value_changed = Signal(object)  # value
    validation_error = Signal(str)  # error_message

    def __init__(self, input_type: str = "price", label: str = "", parent=None):
        """Initialize the trading input widget."""
        super().__init__(parent)

        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

        # Configuration
        self.input_type = input_type  # price, quantity, percentage, premium
        self.label_text = label
        self.is_valid = True
        self.current_value = None

        # Validation rules
        self.validation_rules = self._get_validation_rules()

        # Setup UI
        self.setup_ui()

        # Animation for error states
        self.error_animation = QPropertyAnimation(self, b"geometry")
        self.error_animation.setDuration(100)
        self.error_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_validation_rules(self) -> dict[str, Any]:
        """Get validation rules based on input type."""
        rules = {
            "price": {
                "min": MIN_STRIKE_PRICE,
                "max": MAX_STRIKE_PRICE,
                "decimals": 2,
                "prefix": "$",
                "suffix": ""
            },
            "quantity": {
                "min": MIN_QUANTITY,
                "max": MAX_QUANTITY,
                "decimals": 0,
                "prefix": "",
                "suffix": " contracts"
            },
            "percentage": {
                "min": 0.01,
                "max": 100.0,
                "decimals": 2,
                "prefix": "",
                "suffix": "%"
            },
            "premium": {
                "min": MIN_OPTION_PREMIUM,
                "max": MAX_OPTION_PREMIUM,
                "decimals": 2,
                "prefix": "$",
                "suffix": ""
            }
        }
        return rules.get(self.input_type, rules["price"])

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Label
        if self.label_text:
            self.label = QLabel(self.label_text)
            self.label.setStyleSheet(f"color: {SpyderColors.TEXT}; font-weight: normal;")
            layout.addWidget(self.label)

        # Input container
        input_container = QHBoxLayout()

        # Prefix label
        if self.validation_rules["prefix"]:
            prefix_label = QLabel(self.validation_rules["prefix"])
            prefix_label.setStyleSheet(f"color: {SpyderColors.INFO};")
            input_container.addWidget(prefix_label)

        # Input field
        if self.validation_rules["decimals"] == 0:
            self.input_field = QSpinBox()
            self.input_field.setMinimum(int(self.validation_rules["min"]))
            self.input_field.setMaximum(int(self.validation_rules["max"]))
        else:
            self.input_field = QDoubleSpinBox()
            self.input_field.setMinimum(self.validation_rules["min"])
            self.input_field.setMaximum(self.validation_rules["max"])
            self.input_field.setDecimals(self.validation_rules["decimals"])

        self.input_field.valueChanged.connect(self._on_value_changed)
        input_container.addWidget(self.input_field)

        # Suffix label
        if self.validation_rules["suffix"]:
            suffix_label = QLabel(self.validation_rules["suffix"])
            suffix_label.setStyleSheet(f"color: {SpyderColors.INFO};")
            input_container.addWidget(suffix_label)

        layout.addLayout(input_container)

        # Error message label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {SpyderColors.NEGATIVE}; font-size: 8pt;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.setLayout(layout)

    def _on_value_changed(self, value):
        """Handle value change with validation."""
        self.current_value = value

        # Validate the value
        is_valid, error_message = self._validate_value(value)

        if is_valid:
            self._clear_error_state()
            self.value_changed.emit(value)
        else:
            self._show_error_state(error_message)
            self.validation_error.emit(error_message)

    def _validate_value(self, value) -> tuple[bool, str]:
        """Validate the input value."""
        if value < self.validation_rules["min"]:
            return False, f"Value must be at least {self.validation_rules['min']}"

        if value > self.validation_rules["max"]:
            return False, f"Value must not exceed {self.validation_rules['max']}"

        # Type-specific validation
        if self.input_type == "quantity" and value <= 0:
            return False, "Quantity must be positive"

        if self.input_type == "price" and value <= 0:
            return False, "Price must be positive"

        return True, ""

    def _show_error_state(self, message: str):
        """Show error state with animation."""
        self.is_valid = False

        # Update styling
        self.input_field.setStyleSheet(f"""
            QSpinBox, QDoubleSpinBox {{
                border: 2px solid {SpyderColors.NEGATIVE};
                background-color: rgba(255, 23, 68, 0.1);
            }}
        """)

        # Show error message
        self.error_label.setText(message)
        self.error_label.show()

        # Animate error
        self._animate_error()

    def _clear_error_state(self):
        """Clear error state."""
        self.is_valid = True

        # Reset styling
        self.input_field.setStyleSheet("")

        # Hide error message
        self.error_label.hide()

    def _animate_error(self):
        """Animate widget to indicate error."""
        original_geometry = self.geometry()

        # Shake animation
        shake_geometry = QRect(
            original_geometry.x() + 5,
            original_geometry.y(),
            original_geometry.width(),
            original_geometry.height()
        )

        self.error_animation.setStartValue(original_geometry)
        self.error_animation.setEndValue(shake_geometry)
        self.error_animation.finished.connect(lambda: self.setGeometry(original_geometry))
        self.error_animation.start()

    def set_value(self, value):
        """Set the input value programmatically."""
        self.input_field.setValue(value)

    def get_value(self):
        """Get the current input value."""
        return self.current_value

    def is_valid_input(self) -> bool:
        """Check if current input is valid."""
        return self.is_valid

# ==============================================================================
# ENHANCED SEARCHABLE COMBO BOX
# ==============================================================================
class SpyderSearchableCombo(QWidget):
    """
    Enhanced combo box with search functionality for option symbols.

    Features:
    - Real-time search filtering
    - Trading symbol formatting
    - Recent selections memory
    - Custom item rendering
    """

    # Signals
    selection_changed = Signal(str)  # selected_item

    def __init__(self, items: list[str] = None, parent=None):
        """Initialize the searchable combo box."""
        super().__init__(parent)

        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

        # Configuration
        self.items = items or []
        self.recent_selections = []
        self.max_recent = 5

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Use enhanced combo box if available
        if SUPERQT_AVAILABLE:
            self.combo_box = QSearchableComboBox()
            self.combo_box.addItems(self.items)
            self.combo_box.currentTextChanged.connect(self._on_selection_changed)
        else:
            # Fallback to regular combo box
            self.combo_box = QComboBox()
            self.combo_box.setEditable(True)
            self.combo_box.addItems(self.items)
            self.combo_box.currentTextChanged.connect(self._on_selection_changed)

        layout.addWidget(self.combo_box)
        self.setLayout(layout)

    def _on_selection_changed(self, text: str):
        """Handle selection change."""
        if text and text not in self.recent_selections:
            self.recent_selections.insert(0, text)
            if len(self.recent_selections) > self.max_recent:
                self.recent_selections.pop()

        self.selection_changed.emit(text)

    def add_items(self, items: list[str]):
        """Add items to the combo box."""
        self.items.extend(items)
        self.combo_box.addItems(items)

    def set_items(self, items: list[str]):
        """Set the items in the combo box."""
        self.items = items
        self.combo_box.clear()
        self.combo_box.addItems(items)

    def get_current_text(self) -> str:
        """Get the current selected text."""
        return self.combo_box.currentText()

    def set_current_text(self, text: str):
        """Set the current selected text."""
        index = self.combo_box.findText(text)
        if index >= 0:
            self.combo_box.setCurrentIndex(index)

# ==============================================================================
# ENHANCED COLLAPSIBLE GROUP
# ==============================================================================
class SpyderCollapsibleGroup(QWidget):
    """
    Enhanced collapsible group box for organizing trading parameters.

    Features:
    - Smooth expand/collapse animations
    - Trading-specific styling
    - Memory of collapsed state
    - Custom header with indicators
    """

    # Signals
    expanded_changed = Signal(bool)  # is_expanded

    def __init__(self, title: str = "", expanded: bool = True, parent=None):
        """Initialize the collapsible group."""
        super().__init__(parent)

        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

        # Configuration
        self.title = title
        self.is_expanded = expanded

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Use enhanced group box if available
        if SUPERQT_AVAILABLE:
            self.group_box = QCollapsibleGroupBox(self.title)
            self.group_box.setChecked(self.is_expanded)
            self.group_box.toggled.connect(self._on_expanded_changed)
        else:
            # Fallback to regular group box
            self.group_box = QGroupBox(self.title)
            self.group_box.setCheckable(True)
            self.group_box.setChecked(self.is_expanded)
            self.group_box.toggled.connect(self._on_expanded_changed)

        layout.addWidget(self.group_box)
        self.setLayout(layout)

    def _on_expanded_changed(self, expanded: bool):
        """Handle expand/collapse state change."""
        self.is_expanded = expanded
        self.expanded_changed.emit(expanded)

    def add_widget(self, widget: QWidget):
        """Add a widget to the group."""
        if not self.group_box.layout():
            self.group_box.setLayout(QVBoxLayout())
        self.group_box.layout().addWidget(widget)

    def set_expanded(self, expanded: bool):
        """Set the expanded state."""
        self.group_box.setChecked(expanded)

    def is_group_expanded(self) -> bool:
        """Check if the group is expanded."""
        return self.is_expanded

# ==============================================================================
# TRADING TOOLTIP WIDGET
# ==============================================================================
class SpyderTradingTooltip:
    """
    Enhanced tooltip system for trading data display.

    Features:
    - Rich HTML content
    - Trading data formatting
    - Delayed appearance
    - Position optimization
    """

    @staticmethod
    def show_option_tooltip(widget: QWidget, option_data: dict[str, Any]):
        """Show enhanced tooltip for option data."""
        if not option_data:
            return

        # Format option data
        tooltip_html = f"""
        <div style="background-color: {SpyderColors.PANEL}; color: {SpyderColors.TEXT}; padding: 10px; border: 1px solid {SpyderColors.BORDER};">
            <h3 style="color: {SpyderColors.INFO};">{option_data.get('symbol', 'N/A')}</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td>Strike:</td><td style="color: {SpyderColors.NEUTRAL};">${option_data.get('strike', 0):.2f}</td></tr>
                <tr><td>Bid:</td><td style="color: {SpyderColors.POSITIVE};">${option_data.get('bid', 0):.2f}</td></tr>
                <tr><td>Ask:</td><td style="color: {SpyderColors.NEGATIVE};">${option_data.get('ask', 0):.2f}</td></tr>
                <tr><td>Last:</td><td>${option_data.get('last', 0):.2f}</td></tr>
                <tr><td>Volume:</td><td>{option_data.get('volume', 0):,}</td></tr>
                <tr><td>Open Interest:</td><td>{option_data.get('open_interest', 0):,}</td></tr>
                <tr><td>IV:</td><td>{option_data.get('implied_volatility', 0):.1%}</td></tr>
                <tr><td>Delta:</td><td>{option_data.get('delta', 0):.3f}</td></tr>
                <tr><td>Gamma:</td><td>{option_data.get('gamma', 0):.3f}</td></tr>
                <tr><td>Theta:</td><td>{option_data.get('theta', 0):.3f}</td></tr>
            </table>
        </div>
        """

        # Show tooltip
        QToolTip.showText(widget.mapToGlobal(widget.rect().center()), tooltip_html, widget)

    @staticmethod
    def show_trade_tooltip(widget: QWidget, trade_data: dict[str, Any]):
        """Show enhanced tooltip for trade data."""
        if not trade_data:
            return

        pnl = trade_data.get('pnl', 0)
        pnl_color = SpyderColors.POSITIVE if pnl >= 0 else SpyderColors.NEGATIVE

        tooltip_html = f"""
        <div style="background-color: {SpyderColors.PANEL}; color: {SpyderColors.TEXT}; padding: 10px; border: 1px solid {SpyderColors.BORDER};">
            <h3 style="color: {SpyderColors.INFO};">Trade Details</h3>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td>Symbol:</td><td>{trade_data.get('symbol', 'N/A')}</td></tr>
                <tr><td>Side:</td><td style="color: {SpyderColors.POSITIVE if trade_data.get('side') == 'BUY' else SpyderColors.NEGATIVE};">{trade_data.get('side', 'N/A')}</td></tr>
                <tr><td>Quantity:</td><td>{trade_data.get('quantity', 0)}</td></tr>
                <tr><td>Entry Price:</td><td>${trade_data.get('entry_price', 0):.2f}</td></tr>
                <tr><td>Current Price:</td><td>${trade_data.get('current_price', 0):.2f}</td></tr>
                <tr><td>P&amp;L:</td><td style="color: {pnl_color};">${pnl:.2f}</td></tr>
                <tr><td>Entry Time:</td><td>{trade_data.get('entry_time', 'N/A')}</td></tr>
            </table>
        </div>
        """

        QToolTip.showText(widget.mapToGlobal(widget.rect().center()), tooltip_html, widget)

# ==============================================================================
# WIDGET FACTORY
# ==============================================================================
class SpyderWidgetFactory:
    """Factory class for creating enhanced Spyder widgets."""

    @staticmethod
    def create_strike_range_slider(min_strike: float, max_strike: float) -> SpyderStrikeRangeSlider:
        """Create a strike range slider widget."""
        return SpyderStrikeRangeSlider(min_strike, max_strike)

    @staticmethod
    def create_trading_input(input_type: str, label: str = "") -> SpyderTradingInput:
        """Create a trading input widget."""
        return SpyderTradingInput(input_type, label)

    @staticmethod
    def create_searchable_combo(items: list[str] = None) -> SpyderSearchableCombo:
        """Create a searchable combo box widget."""
        return SpyderSearchableCombo(items)

    @staticmethod
    def create_collapsible_group(title: str, expanded: bool = True) -> SpyderCollapsibleGroup:
        """Create a collapsible group widget."""
        return SpyderCollapsibleGroup(title, expanded)

    @staticmethod
    def is_superqt_available() -> bool:
        """Check if superqt is available."""
        return SUPERQT_AVAILABLE


class TradingMode(Enum):
    """Two trading modes available in the Spyder system.

    PAPER:    Simulated fills against live market data via Tradier sandbox + SpyderR02_PaperEngine.
    LIVE:     Real order execution through Tradier production API + SpyderR04_LiveEngine.
    """

    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass
class MarketData:
    """Lightweight market snapshot for dashboard widgets."""

    symbol: str
    last: float
    change: float
    change_pct: float
    timestamp: datetime


@dataclass
class GreekRisk:
    """Current Greek exposure summary."""

    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass
class ConnectionInfo:
    """Single source of truth for dashboard connection state.

    Per 2026-04-15 audit §16: api_connected and mkt_data_connected used to
    exist as parallel scalar attributes on SpyderTradingDashboard, mutated
    independently of this dataclass. They are now @property accessors that
    read/write the fields below.
    """

    api_connected: bool = False
    mkt_data_connected: bool = False
    bridge_connected: bool = False
    connection_mode: str = "DISCONNECTED"
    market_data_status: str = "NONE"
    trading_active: bool = False
    last_update: datetime | None = None
    last_successful_data: datetime | None = None
    data_was_live: bool = False
    simulation_mode: bool = False


class TrafficLightButton(QPushButton):
    """Custom button that looks like a traffic light with label"""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.status = "green"
        self.setFixedHeight(24)
        self.setMinimumWidth(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding-left: 25px;
                color: #ffffff;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
            }

            QToolTip {
                color: white;
                background-color: #2a2a2a;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 3px;
                font-size: 12px;
            }""",
        )
        self.setText(label)

    def set_status(self, status: str):
        """Set traffic light status: green, yellow, red, blue, purple"""
        self.status = status
        self.update()

    def paintEvent(self, event):
        """Custom paint for traffic light indicator"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        circle_rect = self.rect().adjusted(5, 5, -self.width() + 19, -5)

        if self.status == "green":
            color = QColor(COLORS["positive"])
        elif self.status == "yellow":
            color = QColor(COLORS["warning"])
        elif self.status == "red":
            color = QColor(COLORS["negative"])
        elif self.status == "blue":
            color = QColor(COLORS["blue"])
        elif self.status == "purple":
            color = QColor(COLORS["purple"])
        else:
            color = QColor(COLORS["neutral"])

        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 1))
        painter.drawEllipse(circle_rect)


class SignalMonitorPanel(QWidget):
    """Enhanced Signal Monitor Panel with integrated popup dialogs."""

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self.setFixedHeight(165)
        self.setMinimumWidth(280)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS["panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
            }}
        """,
        )

        layout = QGridLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        self.vix_button = TrafficLightButton("VIX MONITOR")
        self.ai_button = TrafficLightButton("AI DECISION")
        self.gex_button = TrafficLightButton("GEX")
        self.dix_button = TrafficLightButton("DIX")
        self.rsi_button = TrafficLightButton("RSI CONFLUENCE")
        self.risk_button = TrafficLightButton("RISK TRIGGERS")
        self.ogl_button = TrafficLightButton("OGL")
        self.div_button = TrafficLightButton("DIVERGENCE")
        self.dex_button = TrafficLightButton("DEX")
        self.swan_button = TrafficLightButton("BLACK SWAN")
        self.hmm_button = TrafficLightButton("HMM")
        self.skew_button = TrafficLightButton("SKEW")
        self.internals_button = TrafficLightButton("MKT INTERNALS")
        self.regime_button = TrafficLightButton("REGIME")

        layout.addWidget(self.vix_button, 0, 0)
        layout.addWidget(self.ai_button, 0, 1)
        layout.addWidget(self.gex_button, 1, 0)
        layout.addWidget(self.dix_button, 1, 1)
        layout.addWidget(self.rsi_button, 2, 0)
        layout.addWidget(self.risk_button, 2, 1)
        layout.addWidget(self.ogl_button, 3, 0)
        layout.addWidget(self.div_button, 3, 1)
        layout.addWidget(self.dex_button, 4, 0)
        layout.addWidget(self.swan_button, 4, 1)
        layout.addWidget(self.hmm_button, 5, 0)
        layout.addWidget(self.skew_button, 5, 1)
        layout.addWidget(self.internals_button, 6, 0)
        layout.addWidget(self.regime_button, 6, 1)

        self.vix_button.clicked.connect(self.show_vix_dialog)
        self.ai_button.clicked.connect(self.show_ai_dialog)
        self.gex_button.clicked.connect(self.show_gex_dialog)
        self.dix_button.clicked.connect(self.show_dix_dialog)
        self.rsi_button.clicked.connect(self.show_rsi_dialog)
        self.risk_button.clicked.connect(self.show_risk_dialog)
        self.ogl_button.clicked.connect(self.show_ogl_dialog)
        self.div_button.clicked.connect(self.show_div_dialog)
        self.dex_button.clicked.connect(self.show_dex_dialog)
        self.swan_button.clicked.connect(self.show_swan_dialog)
        self.hmm_button.clicked.connect(self.show_hmm_dialog)
        self.skew_button.clicked.connect(self.show_skew_dialog)
        self.internals_button.clicked.connect(self.show_internals_dialog)
        self.regime_button.clicked.connect(self.show_regime_dialog)

        self.setLayout(layout)

        self.current_dialog = None

        self._regime_label = "—"
        self._regime_swan = 1.9
        self._regime_dix = 42.0
        self._regime_skew = 120.0
        self._regime_gex = 0.0
        self.regime_button.set_status("yellow")

        self._live: dict = {}

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_button_states)
        self.update_timer.start(5000)

    def update_live_data(self, data: dict) -> None:
        self._live.update(data)

    def update_button_states(self):
        for button in [
            self.vix_button,
            self.ai_button,
            self.gex_button,
            self.dix_button,
            self.rsi_button,
            self.risk_button,
            self.ogl_button,
            self.div_button,
            self.dex_button,
        ]:
            button.set_status("yellow")

        self.swan_button.set_status("green")
        self.hmm_button.set_status("green")
        self.skew_button.set_status("green")
        self.internals_button.set_status("yellow")

    def close_current_dialog(self):
        if (
            self.current_dialog
            and hasattr(self.current_dialog, "isVisible")
            and self.current_dialog.isVisible()
        ):
            self.current_dialog.close()
            self.current_dialog = None

    def show_signal_dialog(self, signal_type: str):
        self.close_current_dialog()

        if signal_dialog_available and SignalInfoDialog:
            self.current_dialog = SignalInfoDialog(signal_type, self, live_data=self._live)
            parent_pos = self.mapToGlobal(self.rect().topRight())
            self.current_dialog.move(parent_pos.x() + 10, parent_pos.y())
            self.current_dialog.closed.connect(
                lambda: setattr(self, "current_dialog", None),
            )
            self.current_dialog.show()

    def show_vix_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("VIX MONITOR")
        else:
            QMessageBox.information(
                self, "VIX Monitor", "VIX: 15.32\nStatus: Normal\nImplied Move: ±0.96%",
            )

    def show_ai_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("AI DECISION")
        else:
            QMessageBox.information(
                self,
                "AI Decision",
                "Current Signal: NEUTRAL\nConfidence: 72%\nNext Decision: 5 min",
            )

    def show_gex_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("GEX")
        else:
            QMessageBox.information(
                self,
                "GEX Monitor",
                "GEX: -$2.5B\nGamma Flip: 590\nRegime: Negative Gamma",
            )

    def show_dix_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("DIX")
        else:
            QMessageBox.information(
                self, "DIX Monitor", "DIX: 42.5%\nDark Pool: Normal\nSentiment: Neutral",
            )

    def show_rsi_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("RSI CONFLUENCE")
        else:
            QMessageBox.information(
                self, "RSI Confluence", "RSI(14): 52\nRSI(5): 48\nStatus: Neutral Range",
            )

    def show_risk_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("RISK TRIGGERS")
        else:
            QMessageBox.information(
                self,
                "Risk Triggers",
                "Active Triggers: 0\nRisk Level: LOW\nMax Loss Today: -$125",
            )

    def show_ogl_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("OGL")
        else:
            QMessageBox.information(
                self,
                "OGL Monitor",
                "OGL: 585.50\nCurrent SPY: 585.39\nPosition: Below OGL",
            )

    def show_div_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("DIVERGENCE")
        else:
            QMessageBox.information(
                self,
                "Divergence Monitor",
                "Price/RSI: None\nPrice/MACD: None\nStatus: No Divergence",
            )

    def show_dex_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("DEX")
        else:
            QMessageBox.information(
                self, "DEX Monitor", "DEX: $850M\nDelta Neutral: 585\nFlow: Bullish",
            )

    def show_swan_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("BLACK SWAN")
        else:
            QMessageBox.information(
                self,
                "BLACK SWAN Monitor",
                "SWAN Score: 1.85\nRisk Level: LOW\nTail Risk: Minimal",
            )

    def show_hmm_dialog(self):
        if signal_dialog_available:
            self.show_signal_dialog("HMM REGIME")
        else:
            QMessageBox.information(
                self,
                "HMM Regime Detector",
                "The HMM regime dialog is unavailable.\n\n"
                "Connect a supported analytics source or open the signal dialog "
                "when it is available to view live regime data.",
            )

    def show_skew_dialog(self):
        global skew_dialog_available, SkewMonitorDialog
        if skew_dialog_available is None:
            try:
                from Spyder.SpyderG_GUI.SpyderG11_SkewMonitorDialog import (
                    SkewMonitorDialog as _Skew,
                )

                SkewMonitorDialog = _Skew
                skew_dialog_available = True
                logger.info("✅ SKEW Monitor Dialog loaded (lazy)")
            except ImportError:
                SkewMonitorDialog = None
                skew_dialog_available = False
                logger.info("⚠️ SKEW Monitor Dialog not available")

        if skew_dialog_available and SkewMonitorDialog:
            self.close_current_dialog()
            self.current_dialog = SkewMonitorDialog(self)
            self.current_dialog.show()
        elif signal_dialog_available:
            self.show_signal_dialog("SKEW")
        else:
            QMessageBox.information(
                self,
                "SKEW Monitor",
                "The SKEW monitor is unavailable.\n\n"
                "Connect a supported market-data source or open the signal dialog "
                "when it is available to view live SKEW data.",
            )

    def show_internals_dialog(self):
        global internals_dialog_available, MarketInternalsDialog
        if internals_dialog_available is None:
            try:
                from Spyder.SpyderG_GUI.SpyderG17_MarketInternalsWidget import (
                    MarketInternalsDialog as _MID,
                )

                MarketInternalsDialog = _MID
                internals_dialog_available = True
                logger.info("✅ Market Internals Dialog loaded (lazy)")
            except ImportError as exc:
                MarketInternalsDialog = None
                internals_dialog_available = False
                logger.warning("⚠️ Market Internals Dialog not available: %s", exc)

        if internals_dialog_available and MarketInternalsDialog:
            self.close_current_dialog()
            client = getattr(self, "_tradier_client", None)
            if client is None:
                client = getattr(self, "tradier_client", None) or getattr(self, "client", None)
            orch = getattr(self, "_metrics_orchestrator", None)
            self.current_dialog = MarketInternalsDialog(
                tradier_client=client,
                orchestrator=orch,
                parent=self,
            )
            self.current_dialog.show()
        else:
            QMessageBox.information(
                self,
                "Market Internals",
                "TICK / ADD / TRIN monitor unavailable.\n"
                "Ensure SpyderG17_MarketInternalsWidget.py is present and pyqtgraph / yfinance are installed.",
            )

    def update_regime(
        self,
        label: str,
        swan: float,
        dix: float,
        skew: float,
        gex: float,
    ) -> None:
        self._regime_label = label
        self._regime_swan = swan
        self._regime_dix = dix
        self._regime_skew = skew
        self._regime_gex = gex

        self.update_live_data({
            "HMM_LABEL": label,
            "HMM_SWAN": swan,
            "HMM_DIX": dix,
            "HMM_SKEW": skew,
            "HMM_GEX": gex,
        })

        if label in ("EXTREME RISK", "HIGH RISK", "BEARISH"):
            self.regime_button.set_status("red")
        elif label in ("BULLISH", "NEUTRAL BULL"):
            self.regime_button.set_status("green")
        else:
            self.regime_button.set_status("yellow")

    def show_regime_dialog(self) -> None:
        self.close_current_dialog()

        conditions = [
            ("SWAN ≥ 2.0", "EXTREME RISK", COLORS["negative"]),
            ("SWAN ≥ 1.95  or  SKEW ≥ 150", "HIGH RISK", COLORS["negative"]),
            ("SKEW ≥ 140  and  DIX < 42", "CAUTIOUS", COLORS["warning"]),
            ("DIX ≥ 46,  GEX ≥ 0,  SWAN < 1.9", "BULLISH", COLORS["positive"]),
            ("DIX ≤ 40  and  SWAN ≥ 1.85", "BEARISH", COLORS["negative"]),
            ("DIX ≥ 43  and  SWAN < 1.92", "NEUTRAL BULL", COLORS["positive"]),
            ("else", "NEUTRAL", COLORS["warning"]),
        ]

        dlg = QDialog(self)
        dlg.setWindowTitle("Market Regime Classifier")
        dlg.setFixedSize(660, 540)
        dlg.setStyleSheet(
            f"""
            QDialog {{
                background-color: {COLORS["background"]};
                color: {COLORS["text"]};
            }}
            QLabel {{
                color: {COLORS["text"]};
            }}
            QTableWidget {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                gridline-color: {COLORS["border"]};
                border: 1px solid {COLORS["border"]};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: #2a2a2a;
                color: {COLORS["text"]};
                padding: 5px;
                border: 1px solid {COLORS["border"]};
                font-weight: bold;
            }}
            QPushButton {{
                background-color: #2a2a2a;
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
                padding: 6px 20px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            """
        )

        outer = QVBoxLayout(dlg)
        outer.setSpacing(10)
        outer.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Market Regime Classifier")
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #ffffff; padding-bottom: 2px;"
        )
        outer.addWidget(title)

        subtitle = QLabel(
            "Conditions are evaluated top-to-bottom; the first match wins."
        )
        subtitle.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; padding-bottom: 4px;"
        )
        outer.addWidget(subtitle)

        table = QTableWidget(len(conditions), 3)
        table.setHorizontalHeaderLabels(["Condition", "Label", "Colour"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setFixedHeight(len(conditions) * 38 + 34)

        active_row = -1
        bold_font = QFont()
        bold_font.setBold(True)

        for row, (cond_text, label_text, label_color) in enumerate(conditions):
            is_active = label_text == self._regime_label
            if is_active:
                active_row = row
            row_bg = "#1e2e1e" if is_active else COLORS["panel"]

            cond_item = QTableWidgetItem(f"  {cond_text}")
            cond_item.setForeground(QColor(COLORS["text"]))
            cond_item.setBackground(QColor(row_bg))
            if is_active:
                cond_item.setFont(bold_font)
            table.setItem(row, 0, cond_item)

            label_item = QTableWidgetItem(f"  {label_text}")
            label_item.setForeground(QColor(label_color))
            label_item.setBackground(QColor(row_bg))
            if is_active:
                label_item.setFont(bold_font)
            table.setItem(row, 1, label_item)

            if label_color == COLORS["positive"]:
                colour_name = "Green"
            elif label_color == COLORS["negative"]:
                colour_name = "Red"
            else:
                colour_name = "Yellow"
            colour_item = QTableWidgetItem(colour_name)
            colour_item.setForeground(QColor(label_color))
            colour_item.setBackground(QColor(row_bg))
            if is_active:
                colour_item.setFont(bold_font)
            table.setItem(row, 2, colour_item)

        outer.addWidget(table)

        readings = QLabel(
            f"Current readings:  "
            f"SWAN = {self._regime_swan:.2f}   "
            f"DIX = {self._regime_dix:.1f}%   "
            f"SKEW = {self._regime_skew:.0f}   "
            f"GEX = {self._regime_gex:+.2f}"
        )
        readings.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; padding-top: 4px;"
        )
        outer.addWidget(readings)

        regime_color = conditions[active_row][2] if active_row >= 0 else COLORS["warning"]
        active_lbl = QLabel(
            f"Active regime: "
            f"<b style='color: {regime_color};'>{self._regime_label}</b>"
        )
        active_lbl.setTextFormat(Qt.TextFormat.RichText)
        active_lbl.setStyleSheet("font-size: 12px; padding-bottom: 2px;")
        outer.addWidget(active_lbl)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(dlg.close)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

        self.current_dialog = dlg
        dlg.finished.connect(lambda _: setattr(self, "current_dialog", None))
        dlg.show()


class MarketSymbolWidget(QWidget):
    """Widget for displaying a single market symbol."""

    clicked = Signal(str)  # emits the symbol on left-click

    def __init__(self, symbol: str, category: str):
        super().__init__()
        self.symbol = symbol
        self.category = category
        self._last_pmr_state: dict | None = None
        self.setup_ui()

        if symbol in SYMBOL_DESCRIPTIONS:
            self.setToolTip(SYMBOL_DESCRIPTIONS[symbol])
        # Make the row click-targetable for detail dialogs (e.g. PMR).
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.symbol)
        super().mousePressEvent(event)

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 1, 5, 1)

        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        self.symbol_label.setFixedWidth(60)

        self.price_label = QLabel("---.--")
        self.price_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        self.price_label.setFixedWidth(70)
        self.price_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.change_label = QLabel("+0.00")
        self.change_label.setStyleSheet("font-size: 11px;")
        self.change_label.setFixedWidth(55)
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.pct_label = QLabel("0.00%")
        self.pct_label.setStyleSheet("font-size: 11px;")
        self.pct_label.setFixedWidth(55)
        self.pct_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.pct_label)

        self.setLayout(layout)

    def update_data(self, data):
        if isinstance(data, dict):
            last = data.get("last", 0.0)
            change = data.get("change", 0.0)
            change_pct = data.get("change_pct", 0.0)
        else:
            last = data.last
            change = data.change
            change_pct = data.change_pct

        if self.symbol in ["GEX", "DEX", "OGL", "DIX", "SWAN", "NAAIM", "AABULL"]:
            self._update_custom_indicator(last, change, change_pct)
        else:
            self._update_standard_symbol(last, change, change_pct)

    def update_pmr_state(self, state: dict) -> None:
        """Render the S08 Pivot MR signal state in the LAST/CHG/CHG% columns.

        State payload is emitted by R08 every poll. Display modes:
          * DIS    -- producer disabled (SPYDER_PIVOT_MR_ENABLED != 1)
          * N/A    -- S08 module not importable
          * ARMED  -- enabled, watching, signal not yet fired
          * fired  -- arrow + score (e.g. "v R1 72")
        Tooltip shows reasons / penalties for the fired signal.
        """
        if not isinstance(state, dict):
            return
        self._last_pmr_state = dict(state)  # cache for the details dialog
        enabled = bool(state.get("enabled"))
        available = bool(state.get("available"))
        fired = bool(state.get("fired"))
        direction = state.get("direction")
        score = state.get("score")
        level_name = state.get("level_name")
        level_price = state.get("level_price")

        if not available:
            self.price_label.setText("N/A")
            self.price_label.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 11px;"
            )
            self.change_label.setText("\u2014")
            self.change_label.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 11px;"
            )
            self.pct_label.setText("")
            self.pct_label.setStyleSheet("font-size: 11px;")
            self.setToolTip("S08 PivotMeanReversionSignal module not importable")
            return

        if not enabled:
            self.price_label.setText("DIS")
            self.price_label.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 11px;"
            )
            self.change_label.setText("\u2014")
            self.change_label.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 11px;"
            )
            self.pct_label.setText("")
            self.pct_label.setStyleSheet("font-size: 11px;")
            self.setToolTip(
                "Pivot MR producer disabled. Set SPYDER_PIVOT_MR_ENABLED=1 to enable."
            )
            return

        if not fired:
            self.price_label.setText("ARMED")
            self.price_label.setStyleSheet(
                f"color: {COLORS['warning']}; font-size: 11px;"
            )
            self.change_label.setText("\u2014")
            self.change_label.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 11px;"
            )
            self.pct_label.setText("")
            self.pct_label.setStyleSheet("font-size: 11px;")
            self.setToolTip(
                "Pivot MR armed \u2014 watching for fade-resistance / fade-support setup."
            )
            return

        # Fired \u2014 render direction arrow + level + score
        if direction == "fade_resistance":
            arrow = "\u25bc"
            color = COLORS["negative"]
        elif direction == "fade_support":
            arrow = "\u25b2"
            color = COLORS["positive"]
        else:
            arrow = "\u25cf"
            color = COLORS["text"]

        try:
            score_str = f"{float(score):.0f}" if score is not None else "?"
        except (TypeError, ValueError):
            score_str = "?"

        last_text = f"{arrow} {score_str}"
        self.price_label.setText(last_text)
        self.price_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        if level_name and level_price is not None:
            try:
                self.change_label.setText(f"{level_name}@{float(level_price):.1f}")
            except (TypeError, ValueError):
                self.change_label.setText(str(level_name))
        else:
            self.change_label.setText("\u2014")
        self.change_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        self.pct_label.setText("")
        self.pct_label.setStyleSheet("font-size: 11px;")

        # Build tooltip from reasons / penalties for hover detail.
        reasons = state.get("reasons") or []
        penalties = state.get("penalties") or []
        tip_lines: list[str] = []
        if direction:
            tip_lines.append(f"Direction: {direction}")
        if reasons:
            tip_lines.append("Reasons:")
            tip_lines.extend(f"  {r}" for r in reasons)
        if penalties:
            tip_lines.append("Penalties:")
            tip_lines.extend(f"  {p}" for p in penalties)
        self.setToolTip("\n".join(tip_lines) if tip_lines else "Pivot MR fired")

    def _update_standard_symbol(self, last, change, change_pct):
        change_text: str | None = None  # None → use default f"{sign}{change:.2f}"
        if self.symbol.startswith("$"):
            if self.symbol in ("$TICK", "$ADD"):
                self.price_label.setText(f"{last:+.0f}")
                int_color = COLORS["positive"] if last >= 0 else COLORS["negative"]
                self.price_label.setStyleSheet(f"color: {int_color}; font-size: 11px;")
            elif self.symbol == "$TRIN":
                self.price_label.setText(f"{last:.2f}")
                trin_color = COLORS["positive"] if last < 1.0 else COLORS["negative"]
                self.price_label.setStyleSheet(f"color: {trin_color}; font-size: 11px;")
            elif self.symbol == "$VOLD":
                value_m = last / 1_000_000
                sign = "+" if last >= 0 else ""
                self.price_label.setText(f"{sign}{value_m:.1f}M")
                vold_color = COLORS["positive"] if last >= 0 else COLORS["negative"]
                self.price_label.setStyleSheet(f"color: {vold_color}; font-size: 11px;")
                # Scale CHG to M to match the LAST column (same fix as GEX/DEX)
                change_text = self._fmt_compact(change)
            else:
                self.price_label.setText(f"{last:.2f}")
        elif self.symbol in ["SPX", "/ES"]:
            self.price_label.setText(f"{last:.2f}")
        else:
            self.price_label.setText(f"{last:.2f}")

        color = COLORS["positive"] if change >= 0 else COLORS["negative"]
        sign = "+" if change >= 0 else ""

        if change_text is not None:
            self.change_label.setText(change_text)
        else:
            self.change_label.setText(f"{sign}{change:.2f}")
        self.change_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        pct_sign = "+" if change_pct >= 0 else ""
        self.pct_label.setText(f"{pct_sign}{change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    @staticmethod
    def _fmt_compact(value: float) -> str:
        """Format a large dollar value compactly with B/M/K suffix."""
        sign = "+" if value >= 0 else ""
        abs_v = abs(value)
        if abs_v >= 1_000_000_000:
            return f"{sign}{value / 1_000_000_000:.2f}B"
        if abs_v >= 1_000_000:
            return f"{sign}{value / 1_000_000:.1f}M"
        if abs_v >= 1_000:
            return f"{sign}{value / 1_000:.0f}K"
        return f"{sign}{value:.2f}"

    def _update_custom_indicator(self, last, change, change_pct):
        color = COLORS["neutral"]
        change_text: str | None = None  # None → use default f"{sign}{change:.2f}"
        if self.symbol == "GEX":
            value_b = last / 1_000_000_000
            self.price_label.setText(f"{value_b:.1f}B")
            color = COLORS["positive"] if last > 0 else COLORS["negative"]
            change_text = self._fmt_compact(change)
        elif self.symbol == "DEX":
            value_m = last / 1_000_000
            self.price_label.setText(f"{value_m:.0f}M")
            color = COLORS["positive"] if change >= 0 else COLORS["negative"]
            change_text = self._fmt_compact(change)
        elif self.symbol == "OGL":
            self.price_label.setText(f"{last:.2f}")
            color = COLORS["warning"]
        elif self.symbol == "DIX":
            self.price_label.setText(f"{last:.1f}%")
            if last > 45:
                color = COLORS["positive"]
            elif last < 40:
                color = COLORS["negative"]
            else:
                color = COLORS["neutral"]
        elif self.symbol == "SWAN":
            self.price_label.setText(f"{last:.2f}")
            if last < 1.9:
                color = COLORS["positive"]
            elif last < 2.0:
                color = COLORS["warning"]
            else:
                color = COLORS["negative"]
            self.symbol_label.setText("SWAN")
        elif self.symbol == "NAAIM":
            self.price_label.setText(f"{last:.1f}%")
            if last > 90:
                color = COLORS["negative"]
            elif last < 40:
                color = COLORS["warning"]
            else:
                color = COLORS["positive"]
        elif self.symbol == "AABULL":
            self.price_label.setText(f"{last:.1f}%")
            if last < 30:
                color = COLORS["warning"]
            elif last > 50:
                color = COLORS["negative"]
            else:
                color = COLORS["positive"]

        sign = "+" if change >= 0 else ""
        pct_sign = "+" if change_pct >= 0 else ""
        if change_text is not None:
            self.change_label.setText(change_text)
        else:
            self.change_label.setText(f"{sign}{change:.2f}")
        self.change_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.pct_label.setText(f"{pct_sign}{change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color}; font-size: 11px;")


class GreekBar(QWidget):
    """Custom widget for Greek risk display."""

    def __init__(self, name: str, min_val: float, max_val: float):
        super().__init__()
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = 0
        self.percentage = 0
        self.status = "NORMAL"
        self.setFixedHeight(22)

    def set_value(self, value: float, status: str = "NORMAL"):
        self.current_val = value
        # Risk percentage = distance from zero (safe) toward max exposure.
        # This correctly handles asymmetric ranges like Theta (-400, 0) and
        # Vega (-600, 0) where 0 means NO risk and the negative extreme is MAX risk.
        _scale = max(abs(self.min_val), abs(self.max_val))
        self.percentage = abs(value) / _scale if _scale else 0.0
        self.percentage = min(max(self.percentage, 0), 1)
        self.status = status
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(COLORS["background"]))

        bar_rect = QRect(110, 6, self.width() - 300, 10)
        painter.fillRect(bar_rect, QColor(COLORS["panel"]))

        if self.percentage < 0.6:
            color = QColor(COLORS["positive"])
        elif self.percentage < 0.8:
            color = QColor(COLORS["warning"])
        else:
            color = QColor(COLORS["negative"])

        fill_width = int(bar_rect.width() * self.percentage)
        fill_rect = QRect(bar_rect.x(), bar_rect.y(), fill_width, bar_rect.height())
        painter.fillRect(fill_rect, color)

        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRect(bar_rect)

        painter.setPen(QColor(COLORS["text"]))
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)

        text = f"{self.name}: {self.current_val:.2f}"
        painter.drawText(10, 16, text)

        status_rect = QRect(self.width() - 190, 0, 180, 22)
        painter.drawText(
            status_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            self.status,
        )

# ==============================================================================
# TESTING AND DEMONSTRATION
# ==============================================================================
def main():
    """Demonstrate enhanced widgets capabilities."""
    app = QApplication(sys.argv)

    # Apply Spyder styling
    from SpyderU_Utilities.SpyderU24_StyleManager import apply_spyder_style
    apply_spyder_style(app)

    # Create main window
    from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

    window = QMainWindow()
    window.setWindowTitle("Spyder Enhanced Widgets Demo")
    window.setGeometry(100, 100, 800, 600)

    # Central widget
    central_widget = QWidget()
    layout = QVBoxLayout()

    # Create demo widgets
    if SUPERQT_AVAILABLE:
        logging.info("SuperQt available - creating enhanced widgets")

        # Strike range slider
        strike_slider = SpyderWidgetFactory.create_strike_range_slider(400.0, 500.0)
        strike_slider.range_changed.connect(lambda min_val, max_val: logging.debug(f"Strike range: ${min_val:.2f} - ${max_val:.2f}"))
        layout.addWidget(strike_slider)

        # Trading inputs
        price_input = SpyderWidgetFactory.create_trading_input("price", "Entry Price")
        quantity_input = SpyderWidgetFactory.create_trading_input("quantity", "Contracts")

        layout.addWidget(price_input)
        layout.addWidget(quantity_input)

        # Searchable combo
        symbols = ["SPY241220C00450000", "SPY241220P00450000", "SPY241220C00455000"]
        symbol_combo = SpyderWidgetFactory.create_searchable_combo(symbols)
        layout.addWidget(symbol_combo)

        # Collapsible group
        advanced_group = SpyderWidgetFactory.create_collapsible_group("Advanced Options", False)
        advanced_input = SpyderWidgetFactory.create_trading_input("percentage", "Max Risk %")
        advanced_group.add_widget(advanced_input)
        layout.addWidget(advanced_group)

    else:
        logging.info("SuperQt not available - using fallback widgets")
        fallback_label = QLabel("Install superqt for enhanced widgets: pip install superqt")
        fallback_label.setStyleSheet(f"color: {SpyderColors.WARNING}; font-size: 14px; padding: 20px;")
        layout.addWidget(fallback_label)

    central_widget.setLayout(layout)
    window.setCentralWidget(central_widget)
    window.show()

    logging.info("Enhanced widgets demo started")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
