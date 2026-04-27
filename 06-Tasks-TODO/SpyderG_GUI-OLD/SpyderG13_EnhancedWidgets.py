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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QGroupBox, QToolTip, QApplication
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QRect

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
import logging

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
