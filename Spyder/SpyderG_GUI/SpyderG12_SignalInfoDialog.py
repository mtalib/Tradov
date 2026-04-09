#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG12_SignalInfoDialog.py
Group: G (GUI/User Interface)
Purpose: Standardized popup dialogs for Signal Monitor panel
Author: Mohamed Talib
Date Created: 2025-08-13
Last Updated: 2025-08-13 Time: 10:30:00

Description:
    Provides uniform popup dialogs for all 12 signal monitor buttons in the
    trading dashboard. Features consistent sizing (420x380), dark theme styling,
    and auto-close functionality when switching between signals. Each dialog
    displays acronym meaning, concept explanation, signal color interpretations,
    and current status with relevant metrics.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                            QPushButton, QTextEdit, QVBoxLayout, QWidget)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to path for imports
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# ==============================================================================
# CONSTANTS
# ==============================================================================
COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#ff1744",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "cyan": "#00ffff",
    "blue": "#4169E1",
    "purple": "#9370DB",
}

# ==============================================================================
# SIGNAL INFO DIALOG CLASS
# ==============================================================================


class SignalInfoDialog(QDialog):
    """
    Standardized popup dialog for signal monitor buttons.
    Features uniform 420x380 size, dark theme, and auto-close functionality.
    """

    closed = Signal()

    def __init__(self, signal_type: str, parent=None):
        """
        Initialize the signal info dialog.

        Args:
            signal_type: The type of signal (e.g., 'VIX MONITOR', 'GEX', etc.)
            parent: Parent widget
        """
        super().__init__(parent)
        self.signal_type = signal_type
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
        self.load_content()

    def setup_ui(self):
        """Setup the dialog UI with consistent styling"""
        # Fixed size for all popups
        self.setFixedSize(420, 380)

        # Main container with background and border
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, 420, 380)
        self.container.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS['panel']};
                border: 2px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """
        )

        # Main layout
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(15, 10, 15, 15)
        layout.setSpacing(10)

        # Header with title and close button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(0)

        self.title_label = QLabel(self.signal_type)
        self.title_label.setStyleSheet(
            f"""
            color: {COLORS['cyan']};
            font-size: 14px;
            font-weight: normal;
            padding: 5px;
        """
        )
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        # Tiny X close button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_dim']};
                border: none;
                font-size: 14px;
                font-weight: normal;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {COLORS['negative']};
                background-color: rgba(255, 23, 68, 0.1);
                border-radius: 10px;
            }}
        """
        )
        self.close_btn.clicked.connect(self.close)
        header_layout.addWidget(self.close_btn)

        layout.addLayout(header_layout)

        # Separator line
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background-color: {COLORS['border']};")
        layout.addWidget(separator)

        # Content area
        self.content_area = QTextEdit()
        self.content_area.setReadOnly(True)
        self.content_area.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                line-height: 1.5;
            }}
            QTextEdit::verticalScrollBar {{
                width: 8px;
                background-color: {COLORS['background']};
                border: none;
            }}
            QTextEdit::verticalScrollBar::handle {{
                background-color: {COLORS['border']};
                border-radius: 4px;
                min-height: 20px;
            }}
            QTextEdit::verticalScrollBar::handle:hover {{
                background-color: {COLORS['text_dim']};
            }}
        """
        )
        layout.addWidget(self.content_area)

    def load_content(self):
        """Load content based on signal type"""
        content = self.get_signal_content()

        # Format content with HTML for better styling
        formatted_content = self.format_content_html(content)
        self.content_area.setHtml(formatted_content)

    def format_content_html(self, content: dict) -> str:
        """
        Format content dictionary as styled HTML.

        Args:
            content: Dictionary containing signal information

        Returns:
            Formatted HTML string
        """
        html = f"""
        <html>
        <body style="color: {COLORS['text']};">

        <p style="color: {COLORS['cyan']}; font-size: 13px; margin-bottom: 8px;">
        {content['full_name']}<br/>
        <span style="color: {COLORS['text_dim']}; font-size: 11px;">
        {content['description']}
        </span>
        </p>

        <p style="margin-top: 10px; margin-bottom: 8px;">
        <span style="color: {COLORS['warning']};">Concept:</span><br/>
        <span style="color: {COLORS['text']}; font-size: 11px;">
        {content['concept']}
        </span>
        </p>

        <p style="margin-top: 10px; margin-bottom: 8px;">
        <span style="color: {COLORS['warning']};">Signal Colors:</span><br/>
        """

        for color_info in content["signal_colors"]:
            color_style = COLORS[color_info["color"]]
            html += f"""
            <span style="color: {color_style}; font-size: 11px;">
            • {color_info['text']}<br/>
            </span>
            """

        html += f"""
        </p>

        <p style="margin-top: 10px; margin-bottom: 5px;">
        <span style="color: {COLORS['warning']};">Current Status:</span><br/>
        <span style="color: {COLORS['text']}; font-size: 11px; line-height: 1.4;">
        {content['current_status']}
        </span>
        </p>

        </body>
        </html>
        """

        return html

    def get_signal_content(self) -> dict:
        """
        Get content for specific signal type.

        Returns:
            Dictionary containing all signal information
        """

        signal_contents = {
            "VIX MONITOR": {
                "full_name": "VIX - CBOE Volatility Index",
                "description": "Measures 30-day implied volatility of S&P 500 options",
                "concept": "Market's expectation of future volatility, often called the 'fear gauge'",
                "signal_colors": [
                    {"color": "positive", "text": "Green: VIX < 15 (Low volatility, calm markets)"},
                    {"color": "neutral", "text": "Yellow: VIX 15-20 (Normal volatility)"},
                    {"color": "negative", "text": "Red: VIX > 20 (High volatility, market stress)"},
                ],
                "current_status": """VIX: 15.32<br/>
                Implied Daily Move: ±0.96%<br/>
                Market Regime: Normal Volatility""",
            },
            "AI DECISION": {
                "full_name": "AI DECISION ENGINE",
                "description": "Machine Learning-based trade signal generator",
                "concept": "Analyzes multiple indicators using ML models to generate buy/sell signals for SPY options",
                "signal_colors": [
                    {
                        "color": "positive",
                        "text": "Green: Strong directional signal with high confidence",
                    },
                    {"color": "neutral", "text": "Yellow: Neutral or low confidence signal"},
                    {
                        "color": "negative",
                        "text": "Red: Conflicting signals or system recalibration",
                    },
                ],
                "current_status": """Signal: NEUTRAL<br/>
                Confidence: 72%<br/>
                Next Update: 5 minutes<br/>
                Active Models: 4/4""",
            },
            "GEX": {
                "full_name": "GEX - Gamma Exposure",
                "description": "Net gamma exposure of market makers in billions",
                "concept": "Measures hedging pressure from options market makers; negative GEX increases volatility",
                "signal_colors": [
                    {
                        "color": "positive",
                        "text": "Green: Positive GEX (>$1B) - Volatility suppression",
                    },
                    {"color": "neutral", "text": "Yellow: Near zero (-$1B to $1B) - Transitional"},
                    {
                        "color": "negative",
                        "text": "Red: Negative GEX (<-$1B) - Volatility expansion",
                    },
                ],
                "current_status": """GEX: -$2.5B<br/>
                Gamma Flip Level: 590<br/>
                Market Impact: Increased volatility expected<br/>
                Regime: Negative Gamma""",
            },
            "DIX": {
                "full_name": "DIX - Dark Pool Index",
                "description": "Percentage of S&P 500 shares bought in dark pools",
                "concept": "Tracks institutional buying; high DIX suggests smart money accumulation",
                "signal_colors": [
                    {
                        "color": "positive",
                        "text": "Green: DIX > 45% (Bullish institutional buying)",
                    },
                    {"color": "neutral", "text": "Yellow: DIX 40-45% (Neutral)"},
                    {
                        "color": "negative",
                        "text": "Red: DIX < 40% (Bearish, lack of institutional support)",
                    },
                ],
                "current_status": """DIX: 42.5%<br/>
                30-Day Average: 43.2%<br/>
                Sentiment: Neutral<br/>
                Dark Pool Volume: Normal""",
            },
            "RSI CONFLUENCE": {
                "full_name": "RSI - Relative Strength Index Confluence",
                "description": "Multiple timeframe RSI alignment analysis",
                "concept": "Identifies overbought/oversold conditions across different timeframes for better entry/exit timing",
                "signal_colors": [
                    {
                        "color": "positive",
                        "text": "Green: Oversold confluence (<30 on multiple timeframes)",
                    },
                    {"color": "neutral", "text": "Yellow: Neutral range (30-70)"},
                    {
                        "color": "negative",
                        "text": "Red: Overbought confluence (>70 on multiple timeframes)",
                    },
                ],
                "current_status": """RSI(14): 52<br/>
                RSI(5): 48<br/>
                RSI(21): 55<br/>
                Confluence: No extreme conditions""",
            },
            "RISK TRIGGERS": {
                "full_name": "RISK MANAGEMENT TRIGGERS",
                "description": "Automated risk control system status",
                "concept": "Monitors and enforces position limits, drawdowns, and risk parameters to protect capital",
                "signal_colors": [
                    {"color": "positive", "text": "Green: All risk parameters within limits"},
                    {
                        "color": "neutral",
                        "text": "Yellow: Approaching risk limits (75-90% of threshold)",
                    },
                    {"color": "negative", "text": "Red: Risk limit breached, action required"},
                ],
                "current_status": """Active Triggers: 0/8<br/>
                Daily Loss: -$125 (2.5% of limit)<br/>
                Position Delta: 45.5<br/>
                Risk Level: LOW<br/>
                Max Contracts: 5/10 used""",
            },
            "OGL": {
                "full_name": "OGL - Zero Gamma Level",
                "description": "Price level where gamma exposure flips from positive to negative",
                "concept": "Key support/resistance level based on options positioning; acts as a magnet for price",
                "signal_colors": [
                    {"color": "positive", "text": "Green: SPY > OGL + 0.5% (Bullish positioning)"},
                    {"color": "neutral", "text": "Yellow: SPY within ±0.5% of OGL (Neutral zone)"},
                    {"color": "negative", "text": "Red: SPY < OGL - 0.5% (Bearish positioning)"},
                ],
                "current_status": """OGL: 585.50<br/>
                Current SPY: 585.39<br/>
                Distance: -0.11 (-0.02%)<br/>
                Position: Near OGL (Neutral)""",
            },
            "DIVERGENCE": {
                "full_name": "DIVERGENCE DETECTOR",
                "description": "Price vs Indicator divergence analysis",
                "concept": "Identifies when price and indicators move in opposite directions, signaling potential reversals",
                "signal_colors": [
                    {"color": "positive", "text": "Green: No divergence detected"},
                    {"color": "neutral", "text": "Yellow: Weak divergence forming"},
                    {"color": "negative", "text": "Red: Strong divergence confirmed"},
                ],
                "current_status": """Price/RSI: No divergence<br/>
                Price/MACD: No divergence<br/>
                Price/Volume: No divergence<br/>
                Signal Strength: None""",
            },
            "DEX": {
                "full_name": "DEX - Delta Exposure",
                "description": "Net delta exposure of options market in millions",
                "concept": "Measures directional hedging flow; indicates market maker positioning bias",
                "signal_colors": [
                    {"color": "positive", "text": "Green: Positive DEX (>$500M) - Bullish flow"},
                    {"color": "neutral", "text": "Yellow: Neutral (-$500M to $500M)"},
                    {"color": "negative", "text": "Red: Negative DEX (<-$500M) - Bearish flow"},
                ],
                "current_status": """DEX: $850M<br/>
                Delta Neutral Level: 585.00<br/>
                Flow Direction: Bullish<br/>
                1-Day Change: +$125M""",
            },
            "BLACK SWAN": {
                "full_name": "BLACK SWAN RISK INDICATOR",
                "description": "Extreme tail risk monitoring system",
                "concept": "Monitors multiple factors to detect potential for rare, extreme market events",
                "signal_colors": [
                    {"color": "positive", "text": "Green: SWAN Score < 2.0 (Minimal tail risk)"},
                    {"color": "neutral", "text": "Yellow: SWAN Score 2.0-3.0 (Elevated tail risk)"},
                    {
                        "color": "negative",
                        "text": "Red: SWAN Score > 3.0 (Extreme tail risk warning)",
                    },
                ],
                "current_status": """SWAN Score: 1.85<br/>
                Components:<br/>
                - Skew Index: Normal<br/>
                - Put/Call Ratio: Balanced<br/>
                - VIX Term Structure: Normal<br/>
                - Credit Spreads: Tight<br/>
                Risk Level: LOW""",
            },
            "HMM": {
                "full_name": "HMM - Hidden Markov Model Regime Detector",
                "description": "Statistical model identifying market regime states",
                "concept": "Uses probabilistic modeling to identify current market regime (low/normal/high volatility)",
                "signal_colors": [
                    {"color": "positive", "text": "Green: Low volatility regime"},
                    {"color": "neutral", "text": "Yellow: Transitioning between regimes"},
                    {"color": "negative", "text": "Red: High volatility regime"},
                    {"color": "blue", "text": "Blue: Normal regime (stable)"},
                ],
                "current_status": """Current Regime: NORMAL<br/>
                Probability: 0.75<br/>
                Transition Risk: LOW<br/>
                Regime Duration: 12 days<br/>
                Historical Distribution:<br/>
                - Low Vol: 45%<br/>
                - Normal: 40%<br/>
                - High Vol: 15%""",
            },
            "SKEW": {
                "full_name": "SKEW - CBOE SKEW Index",
                "description": "Measures tail risk in S&P 500 options",
                "concept": "Tracks the relative cost of out-of-the-money puts vs calls; high skew indicates elevated tail risk",
                "signal_colors": [
                    {"color": "positive", "text": "Green: SKEW < 125 (Normal tail risk)"},
                    {"color": "neutral", "text": "Yellow: SKEW 125-135 (Elevated tail risk)"},
                    {"color": "negative", "text": "Red: SKEW > 135 (Extreme tail risk)"},
                ],
                "current_status": """CBOE SKEW: 125.5<br/>
                30-Day Average: 124.8<br/>
                Percentile Rank: 55th<br/>
                Tail Risk: Moderate<br/>
                Strategy Impact: Neutral for spreads""",
            },
        }

        return signal_contents.get(
            self.signal_type,
            {
                "full_name": "Unknown Signal",
                "description": "No description available",
                "concept": "No concept available",
                "signal_colors": [],
                "current_status": "No status available",
            },
        )

    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "drag_pos"):
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def closeEvent(self, event):
        """Emit signal when dialog is closed"""
        self.closed.emit()
        super().closeEvent(event)


# ==============================================================================
# MAIN (FOR TESTING)
# ==============================================================================
def main():
    """Test the SignalInfoDialog independently"""
    app = QApplication(sys.argv)

    # Test dialog
    dialog = SignalInfoDialog("GEX")
    dialog.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
