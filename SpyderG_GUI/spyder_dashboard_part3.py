# ==============================================================================
# WIDGET CLASSES 
# ==============================================================================
class TrafficLightButton(QPushButton):
    """Custom button that looks like a traffic light with label"""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.status = "green"
        self.setFixedHeight(24)
        self.setMinimumWidth(120)
        self.setCursor(Qt.PointingHandCursor)
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
            }"""
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
        painter.setRenderHint(QPainter.Antialiasing)

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
    """Enhanced Signal Monitor Panel with integrated popup dialogs"""

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self.setFixedHeight(165)
        self.setMinimumWidth(280)
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """
        )

        layout = QGridLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        # Create all 12 buttons (2x6 grid)
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

        # Add buttons to grid (6 rows, 2 columns)
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

        # Connect buttons to their dialog methods
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

        self.setLayout(layout)

        # Store current dialog reference for auto-close functionality
        self.current_dialog = None

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_button_states)
        self.update_timer.start(5000)

    def update_button_states(self):
        """Update traffic light colors"""
        import random

        # Original 10 buttons
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
            button.set_status(random.choice(["green", "yellow", "red"]))

        # SWAN - weighted probability
        swan_random = random.random()
        if swan_random < 0.85:
            self.swan_button.set_status("green")
        elif swan_random < 0.95:
            self.swan_button.set_status("yellow")
        else:
            self.swan_button.set_status("red")

        # HMM - uses blue/purple for regime states
        hmm_random = random.random()
        if hmm_random < 0.4:
            self.hmm_button.set_status("green")
        elif hmm_random < 0.7:
            self.hmm_button.set_status("blue")
        elif hmm_random < 0.9:
            self.hmm_button.set_status("yellow")
        else:
            self.hmm_button.set_status("red")

        # SKEW - based on tail risk levels
        skew_random = random.random()
        if skew_random < 0.5:
            self.skew_button.set_status("green")
        elif skew_random < 0.8:
            self.skew_button.set_status("yellow")
        else:
            self.skew_button.set_status("red")

    def close_current_dialog(self):
        """Close the currently open dialog if any"""
        if (
            self.current_dialog
            and hasattr(self.current_dialog, "isVisible")
            and self.current_dialog.isVisible()
        ):
            self.current_dialog.close()
            self.current_dialog = None

    def show_signal_dialog(self, signal_type: str):
        """Generic method to show signal dialog with auto-close functionality"""
        self.close_current_dialog()

        if SIGNAL_DIALOG_AVAILABLE:
            self.current_dialog = SignalInfoDialog(signal_type, self)
            # Position the dialog to the right of the signal panel
            parent_pos = self.mapToGlobal(self.rect().topRight())
            self.current_dialog.move(parent_pos.x() + 10, parent_pos.y())
            # Connect the closed signal to clear the reference
            self.current_dialog.closed.connect(
                lambda: setattr(self, "current_dialog", None)
            )
            self.current_dialog.show()

    # Dialog show methods
    def show_vix_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("VIX MONITOR")
        else:
            QMessageBox.information(
                self, "VIX Monitor", "VIX: 15.32\nStatus: Normal\nImplied Move: ±0.96%"
            )

    def show_ai_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("AI DECISION")
        else:
            QMessageBox.information(
                self,
                "AI Decision",
                "Current Signal: NEUTRAL\nConfidence: 72%\nNext Decision: 5 min",
            )

    def show_gex_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("GEX")
        else:
            QMessageBox.information(
                self,
                "GEX Monitor",
                "GEX: -$2.5B\nGamma Flip: 590\nRegime: Negative Gamma",
            )

    def show_dix_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("DIX")
        else:
            QMessageBox.information(
                self, "DIX Monitor", "DIX: 42.5%\nDark Pool: Normal\nSentiment: Neutral"
            )

    def show_rsi_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("RSI CONFLUENCE")
        else:
            QMessageBox.information(
                self, "RSI Confluence", "RSI(14): 52\nRSI(5): 48\nStatus: Neutral Range"
            )

    def show_risk_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("RISK TRIGGERS")
        else:
            QMessageBox.information(
                self,
                "Risk Triggers",
                "Active Triggers: 0\nRisk Level: LOW\nMax Loss Today: -$125",
            )

    def show_ogl_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("OGL")
        else:
            QMessageBox.information(
                self,
                "OGL Monitor",
                "OGL: 585.50\nCurrent SPY: 585.39\nPosition: Below OGL",
            )

    def show_div_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("DIVERGENCE")
        else:
            QMessageBox.information(
                self,
                "Divergence Monitor",
                "Price/RSI: None\nPrice/MACD: None\nStatus: No Divergence",
            )

    def show_dex_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("DEX")
        else:
            QMessageBox.information(
                self, "DEX Monitor", "DEX: $850M\nDelta Neutral: 585\nFlow: Bullish"
            )

    def show_swan_dialog(self):
        if SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("BLACK SWAN")
        else:
            QMessageBox.information(
                self,
                "BLACK SWAN Monitor",
                "SWAN Score: 1.85\nRisk Level: LOW\nTail Risk: Minimal",
            )

    def show_hmm_dialog(self):
        if HMM_DIALOG_AVAILABLE:
            self.close_current_dialog()
            self.current_dialog = HMMMonitorDialog(self)
            self.current_dialog.show()
        elif SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("HMM")
        else:
            QMessageBox.information(
                self,
                "HMM Regime Detector",
                "Current Regime: NORMAL\nProbability: 0.75\nTransition Risk: LOW\n\n"
                "Regime History:\n- Low Vol: 45%\n- Normal: 40%\n- High Vol: 15%",
            )

    def show_skew_dialog(self):
        if SKEW_DIALOG_AVAILABLE:
            self.close_current_dialog()
            self.current_dialog = SkewMonitorDialog(self)
            self.current_dialog.show()
        elif SIGNAL_DIALOG_AVAILABLE:
            self.show_signal_dialog("SKEW")
        else:
            QMessageBox.information(
                self,
                "SKEW Monitor",
                "CBOE SKEW Index: 125.5\nStatus: NORMAL\nTail Risk: Moderate\n\n"
                "Strategy Impact:\n- Puts: Fairly priced\n- Calls: Normal premium\n- Recommended: Iron Condors",
            )


class MarketSymbolWidget(QWidget):
    """Widget for displaying a single market symbol"""

    def __init__(self, symbol: str, category: str):
        super().__init__()
        self.symbol = symbol
        self.category = category
        self.setup_ui()

        if symbol in SYMBOL_DESCRIPTIONS:
            self.setToolTip(SYMBOL_DESCRIPTIONS[symbol])

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 5, 2)

        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"color: {COLORS['text']};")
        self.symbol_label.setFixedWidth(60)

        self.price_label = QLabel("---.--")
        self.price_label.setStyleSheet(f"color: {COLORS['text']};")
        self.price_label.setFixedWidth(70)
        self.price_label.setAlignment(Qt.AlignRight)

        self.change_label = QLabel("+0.00")
        self.change_label.setFixedWidth(55)
        self.change_label.setAlignment(Qt.AlignRight)

        self.pct_label = QLabel("0.00%")
        self.pct_label.setFixedWidth(55)
        self.pct_label.setAlignment(Qt.AlignRight)

        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.pct_label)

        self.setLayout(layout)

    def update_data(self, data):
        """Update display with new data"""
        if isinstance(data, dict):
            last = data.get("last", 0.0)
            change = data.get("change", 0.0)
            change_pct = data.get("change_pct", 0.0)
        else:
            last = data.last
            change = data.change
            change_pct = data.change_pct

        if self.symbol in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
            self._update_custom_indicator(last, change, change_pct)
        else:
            self._update_standard_symbol(last, change, change_pct)

    def _update_standard_symbol(self, last, change, change_pct):
        """Update standard market symbols"""
        if self.symbol.startswith("$"):
            if self.symbol == "$TICK":
                self.price_label.setText(f"{last:+.0f}")
            else:
                self.price_label.setText(f"{last:.2f}")
        elif self.symbol in ["SPX", "/ES"]:
            self.price_label.setText(f"{last:.2f}")
        else:
            self.price_label.setText(f"{last:.2f}")

        color = COLORS["positive"] if change >= 0 else COLORS["negative"]
        sign = "+" if change >= 0 else ""

        self.change_label.setText(f"{sign}{change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")

        self.pct_label.setText(f"{sign}{change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")

    def _update_custom_indicator(self, last, change, change_pct):
        """Update custom indicators with special formatting"""
        if self.symbol == "GEX":
            value_b = last / 1_000_000_000
            self.price_label.setText(f"{value_b:.1f}B")
            color = COLORS["positive"] if last > 0 else COLORS["negative"]
        elif self.symbol == "DEX":
            value_m = last / 1_000_000
            self.price_label.setText(f"{value_m:.0f}M")
            color = COLORS["positive"] if change >= 0 else COLORS["negative"]
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
            self.symbol_label.setText("BSWAN")

        sign = "+" if change >= 0 else ""
        self.change_label.setText(f"{sign}{change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")
        self.pct_label.setText(f"{sign}{change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")


class GreekBar(QWidget):
    """Custom widget for Greek risk display"""

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
        """Update Greek value and status"""
        self.current_val = value
        self.percentage = abs(value - self.min_val) / (self.max_val - self.min_val)
        self.percentage = min(max(self.percentage, 0), 1)
        self.status = status
        self.update()

    def paintEvent(self, event):
        """Custom paint for the Greek bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

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
            Qt.AlignVCenter | Qt.AlignRight,
            self.status,
        )