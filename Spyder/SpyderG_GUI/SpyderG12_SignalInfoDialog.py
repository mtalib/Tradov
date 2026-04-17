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
                            QPushButton, QVBoxLayout, QWidget)

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

    def __init__(self, signal_type: str, parent=None, live_data: dict = None):
        """
        Initialize the signal info dialog.

        Args:
            signal_type: The type of signal (e.g., 'VIX MONITOR', 'GEX', etc.)
            parent: Parent widget
            live_data: Optional dict of live values keyed by symbol name.
        """
        super().__init__(parent)
        self.signal_type = signal_type
        self.live_data = live_data or {}
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
        self.setFixedSize(700, 660)

        # Main container with background and border
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, 700, 660)
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
            font-size: 16px;
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

        # Content area — QLabel renders rich HTML without any scrollbar
        self.content_area = QLabel()
        self.content_area.setWordWrap(True)
        self.content_area.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.content_area.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        self.content_area.setStyleSheet(
            f"""
            QLabel {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 12px;
                font-size: 13px;
            }}
        """
        )
        layout.addWidget(self.content_area)

    def load_content(self):
        """Load content based on signal type"""
        content = self.get_signal_content()

        # Format content with HTML for better styling
        formatted_content = self.format_content_html(content)
        self.content_area.setText(formatted_content)

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
        <body style="color: {COLORS['text']}; font-weight: 400; font-family: inherit;">

        <p style="color: {COLORS['cyan']}; font-size: 15px; font-weight: 400; margin-bottom: 4px;">
        {content['full_name']}<br/>
        <span style="color: {COLORS['text']}; font-size: 13px; font-weight: 400;">
        {content['description']}
        </span>
        </p>

        <p style="margin-top: 10px; margin-bottom: 8px;">
        <span style="color: {COLORS['cyan']}; font-size: 13px; font-weight: 400;">CONCEPT:</span><br/>
        <span style="color: {COLORS['text']}; font-size: 13px; font-weight: 400;">
        {content['concept']}
        </span>
        </p>

        <p style="margin-top: 10px; margin-bottom: 4px;">
        <span style="color: {COLORS['cyan']}; font-size: 13px; font-weight: 400;">SIGNAL COLORS:</span>
        """

        for color_info in content["signal_colors"]:
            color_style = COLORS[color_info["color"]]
            html += f"""
            <p style="color: {color_style}; font-size: 13px; font-weight: 400; margin: 2px 0;">
            • {color_info['text']}
            </p>
            """

        html += f"""
        </p>

        <p style="margin-top: 10px; margin-bottom: 5px;">
        <span style="color: {COLORS['cyan']}; font-size: 13px; font-weight: 400;">CURRENT STATUS:</span><br/>
        <span style="color: {COLORS['text']}; font-size: 13px; font-weight: 400; line-height: 1.6;">
        {content['current_status']}
        </span>
        </p>

        </body>
        </html>
        """

        return html

    def _lv(self, key: str):
        """Return a live value or None if not yet available."""
        v = self.live_data.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def get_signal_content(self) -> dict:
        """
        Get content for specific signal type.

        Returns:
            Dictionary containing all signal information
        """
        # ----------------------------------------------------------------
        # Build live current_status strings where real data is available.
        # Falls back to illustrative static text when no live feed yet.
        # ----------------------------------------------------------------

        # VIX ─────────────────────────────────────────────────────────────
        vix = self._lv("VIX")
        if vix is not None:
            daily_move = vix / 16.0
            if vix < 15:
                vix_regime = "Low Volatility"
            elif vix < 20:
                vix_regime = "Normal Volatility"
            elif vix < 30:
                vix_regime = "High Volatility"
            else:
                vix_regime = "Extreme Volatility"
            vix_status = (
                f"VIX: {vix:.2f}<br/>"
                f"Implied Daily Move: ±{daily_move:.2f}%<br/>"
                f"Market Regime: {vix_regime}"
            )
        else:
            vix_status = "VIX: --<br/>Implied Daily Move: --<br/>Market Regime: --"

        # GEX ─────────────────────────────────────────────────────────────
        gex_raw = self._lv("GEX")  # stored in raw dollars
        if gex_raw is not None:
            gex_b = gex_raw / 1e9
            gex_regime = "Positive Gamma" if gex_b >= 0 else "Negative Gamma"
            gex_impact = "Volatility suppression expected" if gex_b >= 0 else "Increased volatility expected"
            gex_status = (
                f"GEX: {gex_b:+.2f}B<br/>"
                f"Market Impact: {gex_impact}<br/>"
                f"Regime: {gex_regime}"
            )
        else:
            gex_status = "GEX: --<br/>Market Impact: --<br/>Regime: --"

        # DIX ─────────────────────────────────────────────────────────────
        dix = self._lv("DIX")
        if dix is not None:
            if dix > 45:
                dix_sentiment = "Bullish"
            elif dix < 40:
                dix_sentiment = "Bearish"
            else:
                dix_sentiment = "Neutral"
            dix_status = (
                f"DIX: {dix:.1f}%<br/>"
                f"Sentiment: {dix_sentiment}<br/>"
                f"Dark Pool Volume: Normal"
            )
        else:
            dix_status = "DIX: --<br/>Sentiment: --"

        # OGL ─────────────────────────────────────────────────────────────
        ogl = self._lv("OGL")
        spy = self._lv("SPY")
        if ogl is not None:
            ogl_lines = [f"OGL: {ogl:.2f}"]
            if spy is not None:
                dist = spy - ogl
                dist_pct = dist / ogl * 100.0
                pos = "Above OGL (Bullish)" if dist >= 0 else "Below OGL (Bearish)"
                ogl_lines += [
                    f"Current SPY: {spy:.2f}",
                    f"Distance: {dist:+.2f} ({dist_pct:+.2f}%)",
                    f"Position: {pos}",
                ]
            ogl_status = "<br/>".join(ogl_lines)
        else:
            ogl_status = "OGL: --<br/>Current SPY: --"

        # DEX ─────────────────────────────────────────────────────────────
        dex_raw = self._lv("DEX")  # stored in raw dollars
        if dex_raw is not None:
            dex_m = dex_raw / 1e6
            dex_dir = "Bullish" if dex_m >= 0 else "Bearish"
            dex_status = (
                f"DEX: {dex_m:+.0f}M<br/>"
                f"Flow Direction: {dex_dir}"
            )
        else:
            dex_status = "DEX: --<br/>Flow Direction: --"

        # SWAN ────────────────────────────────────────────────────────────
        swan = self._lv("SWAN")
        if swan is not None:
            if swan < 1.9:
                swan_risk = "LOW"
            elif swan < 2.0:
                swan_risk = "ELEVATED"
            else:
                swan_risk = "HIGH"
            swan_status = (
                f"SWAN Score: {swan:.2f}<br/>"
                f"Risk Level: {swan_risk}"
            )
        else:
            swan_status = "SWAN Score: --<br/>Risk Level: --"

        # SKEW ────────────────────────────────────────────────────────────
        skew = self._lv("SKEW")
        if skew is not None:
            if skew < 125:
                skew_risk = "Normal"
            elif skew < 135:
                skew_risk = "Elevated"
            else:
                skew_risk = "Extreme"
            skew_status = (
                f"CBOE SKEW: {skew:.1f}<br/>"
                f"Tail Risk: {skew_risk}"
            )
        else:
            skew_status = "CBOE SKEW: --<br/>Tail Risk: --"

        # HMM REGIME ──────────────────────────────────────────────────────
        # HMM_LABEL and supporting values are pushed by SignalMonitorPanel.update_regime()
        # on every S07 cycle, so they always match what the REGIME button shows.
        hmm_label = self.live_data.get("HMM_LABEL")
        hmm_swan  = self._lv("HMM_SWAN")
        hmm_dix   = self._lv("HMM_DIX")
        hmm_skew  = self._lv("HMM_SKEW")
        hmm_gex   = self._lv("HMM_GEX")
        if hmm_label is not None:
            hmm_lines = [f"Current Regime: {hmm_label}"]
            if hmm_swan is not None:
                hmm_lines.append(f"SWAN Score: {hmm_swan:.2f}")
            if hmm_dix is not None:
                hmm_lines.append(f"DIX: {hmm_dix:.1f}%")
            if hmm_skew is not None:
                hmm_lines.append(f"SKEW: {hmm_skew:.1f}")
            if hmm_gex is not None:
                hmm_lines.append(f"GEX: {hmm_gex / 1e9:+.2f}B")
            hmm_status = "<br/>".join(hmm_lines)
        else:
            hmm_status = (
                "Current Regime: --<br/>"
                "SWAN Score: --<br/>"
                "DIX: --<br/>"
                "SKEW: --"
            )

        # ─────────────────────────────────────────────────────────────────
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
                "current_status": vix_status,
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
                "current_status": (
                    "Signal: NEUTRAL<br/>"
                    "Confidence: 72%<br/>"
                    "Next Update: 5 minutes<br/>"
                    "Active Models: 4/4"
                ),
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
                "current_status": gex_status,
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
                "current_status": dix_status,
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
                "current_status": (
                    "RSI(14): 52<br/>"
                    "RSI(5): 48<br/>"
                    "RSI(21): 55<br/>"
                    "Confluence: No extreme conditions"
                ),
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
                "current_status": (
                    "Active Triggers: 0/8<br/>"
                    "Daily Loss: -$125 (2.5% of limit)<br/>"
                    "Position Delta: 45.5<br/>"
                    "Risk Level: LOW<br/>"
                    "Max Contracts: 5/10 used"
                ),
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
                "current_status": ogl_status,
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
                "current_status": (
                    "Price/RSI: No divergence<br/>"
                    "Price/MACD: No divergence<br/>"
                    "Price/Volume: No divergence<br/>"
                    "Signal Strength: None"
                ),
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
                "current_status": dex_status,
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
                "current_status": swan_status,
            },
            "HMM REGIME": {
                "full_name": "HMM - Hidden Markov Model Regime Detector",
                "description": "Statistical model identifying market regime states",
                "concept": "Uses probabilistic modeling to identify current market regime (low/normal/high volatility)",
                "signal_colors": [
                    {"color": "positive", "text": "Green: Low volatility regime"},
                    {"color": "neutral", "text": "Yellow: Transitioning between regimes"},
                    {"color": "negative", "text": "Red: High volatility regime"},
                    {"color": "blue", "text": "Blue: Normal regime (stable)"},
                ],
                "current_status": hmm_status,
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
                "current_status": skew_status,
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
