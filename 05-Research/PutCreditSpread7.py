# ruff: noqa: T201

import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QDoubleSpinBox, QGroupBox

class PutCreditSpread7(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPY 7 DTE Put Credit Spread Strategy")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Strategy Parameters Group
        params_group = QGroupBox("Strategy Parameters")
        params_layout = QVBoxLayout()

        # Entry Criteria
        entry_layout = QHBoxLayout()
        entry_layout.addWidget(QLabel("Short Put Delta:"))
        self.delta_input = QDoubleSpinBox()
        self.delta_input.setRange(0.01, 0.50)
        self.delta_input.setSingleStep(0.01)
        self.delta_input.setValue(0.10) # Default to 10 Delta
        entry_layout.addWidget(self.delta_input)

        entry_layout.addWidget(QLabel("SMA 200 Filter:"))
        self.sma_filter_checkbox = QCheckBox("SPY above 200-day SMA")
        self.sma_filter_checkbox.setChecked(True)
        entry_layout.addWidget(self.sma_filter_checkbox)
        params_layout.addLayout(entry_layout)

        entry_time_layout = QHBoxLayout()
        entry_time_layout.addWidget(QLabel("Entry Time (ET):"))
        self.entry_time_input = QLineEdit()
        self.entry_time_input.setPlaceholderText("HH:MM")
        self.entry_time_input.setText("15:45")
        entry_time_layout.addWidget(self.entry_time_input)
        params_layout.addLayout(entry_time_layout)

        # Spread Width
        spread_width_layout = QHBoxLayout()
        spread_width_layout.addWidget(QLabel("Spread Width:"))
        self.spread_width_combo = QComboBox()
        self.spread_width_combo.addItems(["$2.50", "$4.00", "$5.00", "$10.00", "$20.00"])
        self.spread_width_combo.setCurrentText("$5.00") # Default to $5 as the SPY best-balance candidate
        spread_width_layout.addWidget(self.spread_width_combo)
        params_layout.addLayout(spread_width_layout)

        # Capital Allocation
        capital_layout = QHBoxLayout()
        capital_layout.addWidget(QLabel("Total Account Capital ($):"))
        self.total_capital_input = QDoubleSpinBox()
        self.total_capital_input.setRange(1000, 1000000)
        self.total_capital_input.setSingleStep(1000)
        self.total_capital_input.setValue(50000) # Default to $50,000
        capital_layout.addWidget(self.total_capital_input)

        capital_layout.addWidget(QLabel("Max Capital per Trade ($):"))
        self.max_trade_capital_input = QDoubleSpinBox()
        self.max_trade_capital_input.setRange(1000, 1000000)
        self.max_trade_capital_input.setSingleStep(1000)
        self.max_trade_capital_input.setValue(20000) # Default to $20,000
        capital_layout.addWidget(self.max_trade_capital_input)
        params_layout.addLayout(capital_layout)

        params_group.setLayout(params_layout)
        main_layout.addWidget(params_group)

        # Exit Rules Group
        exit_group = QGroupBox("Exit Rules")
        exit_layout = QVBoxLayout()

        self.exit_tested_checkbox = QCheckBox("Close if SPY closes below Short Strike")
        self.exit_tested_checkbox.setChecked(True)
        exit_layout.addWidget(self.exit_tested_checkbox)

        hybrid_exit_layout = QHBoxLayout()
        hybrid_exit_layout.addWidget(QLabel("Hybrid Exit (1 DTE):"))
        self.hybrid_exit_checkbox = QCheckBox("Enable Hybrid Exit")
        self.hybrid_exit_checkbox.setChecked(True)
        hybrid_exit_layout.addWidget(self.hybrid_exit_checkbox)

        hybrid_exit_layout.addWidget(QLabel("OTM % for $2.50/$4.00 Widths:"))
        self.otm_25_40_input = QDoubleSpinBox()
        self.otm_25_40_input.setRange(0.01, 10.00)
        self.otm_25_40_input.setSingleStep(0.01)
        self.otm_25_40_input.setValue(2.00) # Default to 2.00%
        hybrid_exit_layout.addWidget(self.otm_25_40_input)

        hybrid_exit_layout.addWidget(QLabel("OTM % for $5.00+ Widths:"))
        self.otm_50_plus_input = QDoubleSpinBox()
        self.otm_50_plus_input.setRange(0.01, 10.00)
        self.otm_50_plus_input.setSingleStep(0.01)
        self.otm_50_plus_input.setValue(0.50) # Default to 0.50%
        hybrid_exit_layout.addWidget(self.otm_50_plus_input)
        exit_layout.addLayout(hybrid_exit_layout)

        exit_group.setLayout(exit_layout)
        main_layout.addWidget(exit_group)

        # Action Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Strategy")
        self.stop_button = QPushButton("Stop Strategy")
        self.stop_button.setEnabled(False) # Initially disabled
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)

        # Status/Log Display (Placeholder)
        self.status_label = QLabel("Status: Ready")
        main_layout.addWidget(self.status_label)

        self.setLayout(main_layout)

        # Connect signals and slots (placeholder for now)
        self.start_button.clicked.connect(self.start_strategy)
        self.stop_button.clicked.connect(self.stop_strategy)

    def start_strategy(self):
        self.status_label.setText("Status: Strategy Started")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        # Here would be the actual logic to start the algo trading strategy
        # This would involve connecting to a broker API, fetching data, calculating strikes, placing orders, etc.
        self.log_parameters()

    def stop_strategy(self):
        self.status_label.setText("Status: Strategy Stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        # Logic to stop the strategy, cancel orders, etc.

    def log_parameters(self):
        print("--- Strategy Parameters ---")
        print(f"Short Put Delta: {self.delta_input.value()}")
        print(f"SMA 200 Filter Enabled: {self.sma_filter_checkbox.isChecked()}")
        print(f"Entry Time (ET): {self.entry_time_input.text()}")
        print(f"Spread Width: {self.spread_width_combo.currentText()}")
        print(f"Total Account Capital: ${self.total_capital_input.value():,.2f}")
        print(f"Max Capital per Trade: ${self.max_trade_capital_input.value():,.2f}")
        print("--- Exit Rules ---")
        print(f"Close if SPY closes below Short Strike: {self.exit_tested_checkbox.isChecked()}")
        print(f"Hybrid Exit Enabled: {self.hybrid_exit_checkbox.isChecked()}")
        print(f"OTM % for $2.50/$4.00 Widths: {self.otm_25_40_input.value()}%")
        print(f"OTM % for $5.00+ Widths: {self.otm_50_plus_input.value()}%")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PutCreditSpread7()
    window.show()
    sys.exit(app.exec())
